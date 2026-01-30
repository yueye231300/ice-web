"""
高原河流虚拟水位测量系统
Mountain River Virtual Water Level Measurement System

基于 ICESat-2 卫星激光测高数据的河流水位监测系统
"""

import streamlit as st
from pathlib import Path
import sys

# 添加 utils 到路径
sys.path.append(str(Path(__file__).parent))

from utils.area_selector import render_area_selector
from utils.icesat2_downloader import render_download_interface
from utils.h5_processor import batch_h5_to_csv
from utils.data_processing_ui import render_data_processing_interface
from utils.water_level_viz import render_water_level_visualization
from utils.storage_manager import StorageManager, render_storage_panel


def initialize_session():
    """初始化 session state"""
    if "data_downloaded" not in st.session_state:
        st.session_state.data_downloaded = False

    if "data_processed" not in st.session_state:
        st.session_state.data_processed = False

    if "current_bbox" not in st.session_state:
        st.session_state.current_bbox = None

    if "current_geometry" not in st.session_state:
        st.session_state.current_geometry = None

    if "icesat2_data" not in st.session_state:
        st.session_state.icesat2_data = None

    if "processed_data" not in st.session_state:
        st.session_state.processed_data = None

    if "csv_dir" not in st.session_state:
        st.session_state.csv_dir = None


# 页面配置
st.set_page_config(
    page_title="高原河流虚拟水位测量",
    layout="wide",
    initial_sidebar_state="expanded",
)


def render_header():
    """渲染页面头部"""
    st.title("高原河流虚拟水位测量系统")
    st.markdown(
        """
    基于 **ICESat-2** 卫星激光测高数据的河流水位监测系统。
    
    **主要功能:**
    - 灵活的区域选择（交互式地图、坐标+缓冲区、边界框、Shapefile）
    - ICESat-2 数据自动下载
    - 多种数据处理方法： DBSCAN 聚类、滑动中位数、百分位数过滤
    - 虚拟水位测站可视化
    - 水位数据分析与导出
    """
    )


def render_sidebar():
    """渲染侧边栏"""
    with st.sidebar:
        st.image("https://img.icons8.com/color/96/000000/mountain.png", width=80)
        st.title("系统控制面板")

        st.markdown("---")

        # 存储管理面板
        with st.expander("数据存储管理", expanded=False):
            render_storage_panel()

        st.markdown("---")

        # 工作流程状态
        st.subheader("工作流程")

        steps = {
            "1. 区域选择": st.session_state.current_bbox is not None,
            "2. 数据下载": st.session_state.data_downloaded,
            "3. 数据处理": st.session_state.data_processed,
            "4. 结果展示": st.session_state.processed_data is not None,
        }

        for step, completed in steps.items():
            if completed:
                st.success(f"[完成] {step}")
            else:
                st.info(f"[等待] {step}")

        st.markdown("---")

        # 帮助信息
        with st.expander("使用帮助"):
            st.markdown(
                """
            **使用步骤:**
            
            1. **区域选择**: 选择研究区域
               - 坐标+缓冲区：输入中心点和半径
               - 边界框：输入矩形范围
               - Shapefile：上传矢量文件
            
            2. **数据下载**: 下载 ICESat-2 数据
               - 选择时间范围
               - 选择产品类型（推荐 ATL13）
            
            3. **H5 转换**: 将 H5 文件转换为 CSV
            
            4. **数据处理**: 使用多种统计方法处理数据
                - DBSCAN 聚类
                - 滑动中位数过滤
                - 百分位数过滤
            
            5. **结果展示**: 查看虚拟测站和水位数据
            """
            )

        with st.expander("关于"):
            st.markdown(
                """
            **版本**: 1.0.0  
            **开发**: Yan Lab  
            **技术栈**: 
            - ICESat-2
            - Streamlit
            - Folium
            """
            )


def main():
    """主函数"""
    # 初始化 session state
    initialize_session()

    # 渲染页面
    render_header()
    render_sidebar()

    st.markdown("---")

    # 主要内容区域 - 使用标签页
    tab1, tab2, tab3, tab4, tab5 = st.tabs(
        ["1️⃣ 区域选择", "2️⃣ 数据下载", "3️⃣ H5 转换", "4️⃣ 数据处理", "5️⃣ 结果展示"]
    )

    with tab1:
        geometry, bbox = render_area_selector()
        if geometry is not None and bbox is not None:
            # 检查研究区域是否改变
            bbox_changed = (
                st.session_state.current_bbox is None
                or st.session_state.current_bbox != bbox
            )

            if bbox_changed:
                # 研究区域改变，清理旧数据
                if st.session_state.current_bbox is not None:
                    storage = StorageManager()
                    storage.clear_session_data()

                    # 重置状态
                    st.session_state.data_downloaded = False
                    st.session_state.data_processed = False
                    st.session_state.icesat2_data = None
                    st.session_state.processed_data = None
                    st.session_state.download_dir = None
                    st.session_state.csv_dir = None
                    if "processing_stats" in st.session_state:
                        del st.session_state.processing_stats
                    st.info("研究区域已更新，请重新开始分析流程")

            # 更新当前区域
            st.session_state.current_geometry = geometry
            st.session_state.current_bbox = bbox

    with tab2:
        render_download_interface()

    with tab3:
        st.subheader("H5 文件转换为 CSV")
        st.info("将下载的 H5 文件转换为 CSV 格式，便于后续处理")

        if not st.session_state.data_downloaded:
            st.warning("请先下载 ICESat-2 数据")
        else:
            # 显示当前会话的数据信息
            storage = StorageManager()
            h5_dir = storage.get_data_dir("h5")
            h5_files = list(h5_dir.glob("*.h5"))

            if h5_files:
                st.success(f"当前会话中有 {len(h5_files)} 个 H5 文件")
                with st.expander("查看 H5 文件列表"):
                    for f in h5_files:
                        st.write(
                            f"- {f.name} ({f.stat().st_size / 1024 / 1024:.2f} MB)"
                        )
            else:
                st.warning("未找到 H5 文件，请检查下载是否成功")

            if st.button("开始转换", type="primary"):
                with st.spinner("正在转换文件..."):
                    count = batch_h5_to_csv(input_dir=h5_dir)

                    if count > 0:
                        csv_dir = storage.get_data_dir("csv")
                        st.session_state.csv_dir = csv_dir

    with tab4:

        render_data_processing_interface()

    with tab5:
        render_water_level_visualization()

    # 页脚
    st.markdown("---")
    st.markdown(
        "<div style='text-align: center; color: gray;'>"
        "Highland River Virtual Water Level Measurement System | "
        "</div>",
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
