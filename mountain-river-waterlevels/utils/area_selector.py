"""
区域选择工具模块
支持四种方式：交互式地图选择、坐标+半径、边界框、Shapefile上传
"""

import geopandas as gpd
import streamlit as st
from shapely.geometry import Point, box, mapping
from typing import Tuple, Optional, List
import tempfile
import os
import folium
from streamlit_folium import st_folium
from folium.plugins import Draw


def create_buffer_geometry(
    lon: float, lat: float, radius_km: float
) -> Tuple[dict, List[float]]:
    """
    根据坐标和半径创建缓冲区

    Args:
        lon: 经度
        lat: 纬度
        radius_km: 缓冲区半径（公里）

    Returns:
        Tuple[dict, List[float]]: (GeoJSON几何对象, bbox)
    """
    point = Point(lon, lat)
    # 转换为度数近似（1度约111km）
    buffer_deg = radius_km / 111.0
    buffer = point.buffer(buffer_deg)

    bounds = buffer.bounds  # (minx, miny, maxx, maxy)
    bbox = [bounds[0], bounds[1], bounds[2], bounds[3]]
    geojson = mapping(buffer)

    return geojson, bbox


def shp_to_geometry(
    shp_file,
) -> Tuple[Optional[dict], Optional[List[float]], Optional[str]]:
    """
    将上传的 SHP 文件转换为 GeoJSON 几何对象

    Args:
        shp_file: Streamlit 上传的文件对象

    Returns:
        Tuple[dict, List[float], str]: (GeoJSON几何对象, bbox, 错误信息)
    """
    try:
        # 创建临时目录保存上传的文件
        with tempfile.TemporaryDirectory() as tmp_dir:
            # 保存 shp 文件
            shp_path = os.path.join(tmp_dir, shp_file.name)
            with open(shp_path, "wb") as f:
                f.write(shp_file.getbuffer())

            # 读取 shapefile
            gdf = gpd.read_file(shp_path)

            # 确保是 WGS84 坐标系
            if gdf.crs is None:
                return None, None, "Shapefile 缺少坐标系信息"

            if gdf.crs.to_epsg() != 4326:
                gdf = gdf.to_crs(epsg=4326)

            # 合并所有几何为一个
            geom = gdf.unary_union

            # 转换为 GeoJSON
            geojson = mapping(geom)

            # 获取边界框
            bounds = geom.bounds  # (minx, miny, maxx, maxy)
            bbox = [bounds[0], bounds[1], bounds[2], bounds[3]]

            return geojson, bbox, None

    except Exception as e:
        return None, None, f"读取 Shapefile 失败: {str(e)}"


def bbox_to_geometry(
    min_lon: float, min_lat: float, max_lon: float, max_lat: float
) -> Tuple[dict, List[float]]:
    """
    根据边界框坐标创建几何对象

    Args:
        min_lon: 最小经度
        min_lat: 最小纬度
        max_lon: 最大经度
        max_lat: 最大纬度

    Returns:
        Tuple[dict, List[float]]: (GeoJSON几何对象, bbox)
    """
    bbox_geom = box(min_lon, min_lat, max_lon, max_lat)
    geojson = mapping(bbox_geom)
    bbox = [min_lon, min_lat, max_lon, max_lat]
    return geojson, bbox


def render_interactive_map() -> Tuple[Optional[dict], Optional[List[float]]]:
    """
    渲染交互式地图，允许用户绘制选择区域

    Returns:
        Tuple[dict, List[float]]: (GeoJSON几何对象, bbox)
    """
    st.info("在地图上绘制矩形或多边形来选择研究区域")

    # 初始化地图中心
    col1, col2 = st.columns(2)
    with col1:
        center_lat = st.number_input(
            "地图中心纬度", value=30.0, min_value=-90.0, max_value=90.0, format="%.4f"
        )
    with col2:
        center_lon = st.number_input(
            "地图中心经度",
            value=102.0,
            min_value=-180.0,
            max_value=180.0,
            format="%.4f",
        )

    # 创建 Folium 地图
    m = folium.Map(
        location=[center_lat, center_lon], zoom_start=8, tiles="OpenStreetMap"
    )

    # 添加绘制工具
    Draw(
        export=True,
        draw_options={
            "polyline": False,
            "polygon": True,
            "rectangle": True,
            "circle": False,
            "marker": False,
            "circlemarker": False,
        },
        edit_options={"edit": True},
    ).add_to(m)

    # 渲染地图
    output = st_folium(m, width=700, height=500)

    geometry = None
    bbox = None

    # 检查是否有绘制的图形
    if output and "all_drawings" in output and output["all_drawings"]:
        drawings = output["all_drawings"]
        if len(drawings) > 0:
            # 取最后一个绘制的图形
            last_drawing = drawings[-1]

            try:
                if last_drawing["geometry"]["type"] == "Polygon":
                    geometry = last_drawing["geometry"]
                    coords = geometry["coordinates"][0]

                    # 计算 bbox
                    lons = [coord[0] for coord in coords]
                    lats = [coord[1] for coord in coords]
                    bbox = [min(lons), min(lats), max(lons), max(lats)]

                    st.success(
                        f"已选择区域：范围 [{bbox[0]:.4f}, {bbox[1]:.4f}, {bbox[2]:.4f}, {bbox[3]:.4f}]"
                    )
                    st.info(
                        f"区域大小：约 {abs(bbox[2]-bbox[0]):.4f}° × {abs(bbox[3]-bbox[1]):.4f}°"
                    )

            except Exception as e:
                st.warning(f"解析绘制区域时出错：{str(e)}")
    else:
        st.warning("请在地图上使用工具绘制一个矩形或多边形区域")

    return geometry, bbox


def render_area_selector() -> Tuple[Optional[dict], Optional[List[float]]]:
    """
    渲染区域选择器界面

    Returns:
        Tuple[dict, List[float]]: (GeoJSON几何对象, bbox)
    """
    st.subheader("选择研究区域")

    method = st.radio(
        "选择区域定义方式",
        ["交互式地图选择", "坐标 + 缓冲区", "边界框 (BBox)", "上传 Shapefile"],
        horizontal=False,
    )

    geometry = None
    bbox = None

    if method == "交互式地图选择":
        return render_interactive_map()

    elif method == "坐标 + 缓冲区":
        col1, col2, col3 = st.columns(3)
        with col1:
            lon = st.number_input(
                "经度", value=102.0, min_value=-180.0, max_value=180.0, format="%.6f"
            )
        with col2:
            lat = st.number_input(
                "纬度", value=30.0, min_value=-90.0, max_value=90.0, format="%.6f"
            )
        with col3:
            radius = st.number_input(
                "缓冲区半径 (km)", value=10.0, min_value=0.1, max_value=100.0, step=0.1
            )

        if st.button("创建缓冲区"):
            geometry, bbox = create_buffer_geometry(lon, lat, radius)
            st.success(f"缓冲区已创建：中心点 ({lon:.4f}, {lat:.4f})，半径 {radius} km")

    elif method == "边界框 (BBox)":
        col1, col2 = st.columns(2)
        with col1:
            min_lon = st.number_input(
                "最小经度",
                value=101.0,
                min_value=-180.0,
                max_value=180.0,
                format="%.6f",
            )
            min_lat = st.number_input(
                "最小纬度", value=29.0, min_value=-90.0, max_value=90.0, format="%.6f"
            )
        with col2:
            max_lon = st.number_input(
                "最大经度",
                value=103.0,
                min_value=-180.0,
                max_value=180.0,
                format="%.6f",
            )
            max_lat = st.number_input(
                "最大纬度", value=31.0, min_value=-90.0, max_value=90.0, format="%.6f"
            )

        if st.button("创建边界框"):
            if min_lon >= max_lon or min_lat >= max_lat:
                st.error("请确保最小值小于最大值")
            else:
                geometry, bbox = bbox_to_geometry(min_lon, min_lat, max_lon, max_lat)
                st.success(
                    f"边界框已创建：[{min_lon:.4f}, {min_lat:.4f}, {max_lon:.4f}, {max_lat:.4f}]"
                )

    else:  # 上传 Shapefile
        st.info("请上传 .shp 文件及其配套文件（.shx, .dbf, .prj 等）")
        shp_file = st.file_uploader("上传 Shapefile (.shp)", type=["shp"])

        if shp_file is not None:
            if st.button("加载 Shapefile"):
                with st.spinner("正在处理 Shapefile..."):
                    geometry, bbox, error = shp_to_geometry(shp_file)
                    if error:
                        st.error(f"{error}")
                    else:
                        st.success(f"Shapefile 已加载，范围：{bbox}")

    return geometry, bbox
