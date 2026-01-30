"""
虚拟水位测站可视化模块
"""

import pandas as pd
import folium
from folium import plugins
import streamlit as st
from streamlit_folium import st_folium
import plotly.graph_objects as go
from typing import Optional
from datetime import datetime


def create_water_level_map(df: pd.DataFrame) -> folium.Map:
    """
    创建水位测站地图 - 显示所有筛选后的水位点

    Args:
        df: 包含经纬度和水位数据的 DataFrame

    Returns:
        folium.Map: 地图对象
    """
    # 创建数据副本
    df = df.copy()

    # 检查必需的列
    required_cols = ["lat", "lon", "ht_water_surf"]
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        raise ValueError(f"数据缺少必需的列: {missing_cols}")

    # 清洗数据
    df = df.dropna(subset=["lat", "lon", "ht_water_surf"])
    df["lat"] = pd.to_numeric(df["lat"], errors="coerce")
    df["lon"] = pd.to_numeric(df["lon"], errors="coerce")
    df["ht_water_surf"] = pd.to_numeric(df["ht_water_surf"], errors="coerce")
    df = df.dropna(subset=["lat", "lon", "ht_water_surf"])

    if len(df) == 0:
        raise ValueError("没有有效的数据点")

    # 计算地图中心点
    center_lat = df["lat"].mean()
    center_lon = df["lon"].mean()

    # 创建地图
    m = folium.Map(
        location=[center_lat, center_lon], zoom_start=12, tiles="OpenStreetMap"
    )

    # 添加所有水位点作为圆形标记
    for idx, row in df.iterrows():
        folium.CircleMarker(
            location=[row["lat"], row["lon"]],
            radius=5,
            popup=f"水位: {row['ht_water_surf']:.3f} m",
            color="blue",
            fill=True,
            fillColor="lightblue",
            fillOpacity=0.6,
            weight=1,
        ).add_to(m)

    return m


def plot_water_level_distribution(df: pd.DataFrame):
    """
    绘制水位分布图

    Args:
        df: 包含水位数据的 DataFrame
    """
    if "ht_water_surf" not in df.columns:
        st.warning("数据中没有水位信息")
        return

    # 移除 NaN 值
    valid_data = df["ht_water_surf"].dropna()

    if len(valid_data) == 0:
        st.warning("没有有效的水位数据")
        return

    fig = go.Figure()

    # 直方图
    fig.add_trace(
        go.Histogram(x=valid_data, nbinsx=30, name="水位分布", marker_color="lightblue")
    )

    # 添加均值线
    mean_val = valid_data.mean()
    fig.add_vline(
        x=mean_val,
        line_dash="dash",
        line_color="red",
        annotation_text=f"平均值: {mean_val:.2f} m",
    )

    fig.update_layout(
        title="水位高程分布",
        xaxis_title="水位高程 (m)",
        yaxis_title="频次",
        showlegend=True,
        height=400,
    )

    st.plotly_chart(fig, use_container_width=True)


def plot_water_level_time_series(df: pd.DataFrame):
    """
    绘制水位时间序列

    Args:
        df: 包含时间和水位数据的 DataFrame
    """
    if "delta_time" not in df.columns or "ht_water_surf" not in df.columns:
        st.warning("缺少时间或水位数据")
        return

    # 移除 NaN 值
    valid_df = df[["delta_time", "ht_water_surf"]].dropna()

    if len(valid_df) == 0:
        st.warning("没有有效的时间序列数据")
        return

    # 按时间排序
    valid_df = valid_df.sort_values("delta_time")

    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=valid_df["delta_time"],
            y=valid_df["ht_water_surf"],
            mode="markers",
            name="观测点",
            marker=dict(size=5, color="blue", opacity=0.6),
        )
    )

    fig.update_layout(
        title="水位时间序列",
        xaxis_title="时间 (delta_time)",
        yaxis_title="水位高程 (m)",
        showlegend=True,
        height=400,
    )

    st.plotly_chart(fig, width="stretch")


def display_station_statistics(df: pd.DataFrame):
    """
    显示测站统计信息

    Args:
        df: 包含水位数据的 DataFrame
    """
    st.subheader("统计信息")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("总观测点数", f"{len(df):,}")

    with col2:
        if "ht_water_surf" in df.columns:
            # 使用中间50%计算均值
            heights = df["ht_water_surf"].dropna()
            if len(heights) >= 4:
                q25_idx = int(len(heights) * 0.25)
                q75_idx = int(len(heights) * 0.75)
                sorted_heights = heights.sort_values()
                middle_heights = sorted_heights.iloc[q25_idx:q75_idx]
                mean_height = middle_heights.mean()
            else:
                mean_height = heights.mean()
            st.metric("平均水位 (中间50%)", f"{mean_height:.3f} m")

    with col3:
        if "ht_water_surf" in df.columns:
            std_height = df["ht_water_surf"].std()
            st.metric("水位标准差", f"{std_height:.3f} m")

    with col4:
        # 计算虚拟测站数量
        df_temp = df.copy()
        df_temp["lat_rounded"] = df_temp["lat"].round(3)
        df_temp["lon_rounded"] = df_temp["lon"].round(3)
        n_stations = len(df_temp.groupby(["lat_rounded", "lon_rounded"]).size())
        st.metric("虚拟测站数", f"{n_stations}")


def render_water_level_visualization():
    """
    渲染水位可视化界面
    """
    st.header("高原河流虚拟水位测站")

    if not st.session_state.data_processed:
        st.warning("请先完成数据处理")
        st.info(
            """
        **工作流程：**
        1. 区域选择
        2. 下载 ICESat-2 数据
        3. 转换 H5 为 CSV
        4. 使用 DBSCAN/滑动中位数/百分位数方法处理数据
        5. 在此查看结果
        """
        )
        return

    if st.session_state.processed_data is None or st.session_state.processed_data.empty:
        st.warning("没有可用的处理数据")
        return

    df = st.session_state.processed_data

    # 统计信息
    avg_water_level = df["ht_water_surf"].mean()

    # 显示概览信息
    col1, col2 = st.columns(2)
    with col1:
        st.info(f"💧 共 {len(df)} 个筛选后的水位点")
    with col2:
        st.success(
            f"📊 平均水位: {avg_water_level:.3f} m (\u5b8c整值: {avg_water_level:.6f} m)"
        )

    # 地图可视化
    st.subheader("水位点分布地图")
    try:
        water_map = create_water_level_map(df)
        st_folium(water_map, width=None, height=600)
    except Exception as e:
        st.error(f"地图创建失败: {str(e)}")
    st.markdown("---")

    # 数据分析
    plot_water_level_distribution(df)

    st.markdown("---")

    # 数据预览
    st.subheader("数据预览")
    st.dataframe(df.head(100), width="stretch")

    # 下载按钮
    st.download_button(
        label="下载完整数据 (CSV)",
        data=df.to_csv(index=False),
        file_name=f"virtual_water_stations_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        mime="text/csv",
        type="primary",
    )
