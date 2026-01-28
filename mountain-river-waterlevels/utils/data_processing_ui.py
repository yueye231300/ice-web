"""
数据处理界面模块
提供多种水位数据处理方法的界面
"""

import streamlit as st
import plotly.graph_objects as go
from pathlib import Path
from utils.data_processor import (
    batch_process_csv_files,
    calculate_water_level_statistics,
)


def plot_filtering_comparison(total: int, kept: int):
    """
    绘制过滤统计饼图

    Args:
        total: 总点数
        kept: 保留点数
    """
    if total == 0:
        return

    removed = total - kept

    fig = go.Figure(
        data=[
            go.Pie(
                labels=["保留", "过滤"],
                values=[kept, removed],
                hole=0.4,
                marker_colors=["#2E86AB", "#E63946"],
            )
        ]
    )

    fig.update_layout(title=f"数据过滤结果 (保留率: {kept/total*100:.1f}%)", height=400)

    st.plotly_chart(fig, width="container")


def plot_height_distribution(df, title="水位高程分布"):
    """
    绘制水位分布直方图

    Args:
        df: 包含水位数据的DataFrame
        title: 图表标题
    """
    if df.empty or "ht_water_surf" not in df.columns:
        st.warning("没有水位数据")
        return

    heights = df["ht_water_surf"].dropna()

    fig = go.Figure()

    fig.add_trace(
        go.Histogram(x=heights, nbinsx=50, name="水位分布", marker_color="lightblue")
    )

    # 添加均值线
    mean_val = heights.mean()
    median_val = heights.median()

    fig.add_vline(
        x=mean_val,
        line_dash="dash",
        line_color="red",
        annotation_text=f"均值: {mean_val:.3f} m",
    )

    fig.add_vline(
        x=median_val,
        line_dash="dot",
        line_color="green",
        annotation_text=f"中位数: {median_val:.3f} m",
    )

    fig.update_layout(
        title=title,
        xaxis_title="水位高程 (m)",
        yaxis_title="频次",
        showlegend=True,
        height=400,
    )

    st.plotly_chart(fig, width="stretch")


def render_data_processing_interface():
    """
    渲染数据处理界面
    """
    st.header("ICESat-2 数据处理")

    # 检查前置条件
    if not st.session_state.data_downloaded:
        st.warning("请先下载 ICESat-2 数据")
        st.info(
            """
        **工作流程：**
        1. 在"区域选择"中定义研究区域
        2. 在"数据下载"中下载 ICESat-2 数据
        3. 转换 H5 文件为 CSV
        4. 在此进行数据处理和噪声过滤
        """
        )
        return

    # 检查CSV文件
    if hasattr(st.session_state, "download_dir"):
        csv_dir = st.session_state.download_dir.parent / "csv"
        csv_files = list(csv_dir.glob("*.csv")) if csv_dir.exists() else []

        if not csv_files:
            st.warning("未找到 CSV 文件，请先将 H5 转换为 CSV")
            st.info("在左侧边栏的 'H5 转 CSV' 部分进行转换")
            return

        st.success(f"找到 {len(csv_files)} 个 CSV 文件")

        # 方法选择
        st.subheader("选择处理方法")

        method_choice = st.radio(
            "数据处理算法",
            [
                "DBSCAN 椭圆邻域聚类（推荐用于复杂地形）",
                "滑动中位数过滤",
                "百分位数过滤",
            ],
            help="根据数据特征选择合适的处理方法",
        )

        # 方法说明和参数设置
        if "DBSCAN" in method_choice:
            st.info(
                """
            **DBSCAN 椭圆邻域聚类**
            
            - 核心思想：水面光子在空间上高密度聚集，噪声光子稀疏分布
            - 适用场景：信噪比极低、地形极其复杂的山区河流
            - 优势：能有效识别和排除噪声，适应条带状数据特征
            """
            )

            col1, col2, col3 = st.columns(3)
            with col1:
                eps_along = st.slider(
                    "沿轨邻域半径 (m)",
                    10.0,
                    200.0,
                    50.0,
                    5.0,
                    help="""定义椭圆邻域的长轴半径（沿卫星轨道方向）。
                    - 较大值：能连接更远的点，适合稀疏数据
                    - 较小值：更严格的聚类，适合密集数据
                    - 推荐：50-100m 用于河流场景""",
                )
            with col2:
                eps_height = st.slider(
                    "高程邻域半径 (m)",
                    0.5,
                    10.0,
                    2.0,
                    0.5,
                    help="""定义椭圆邻域的短轴半径（垂直高程方向）。
                    - 较大值：容忍更大的高程差异
                    - 较小值：更严格的高程一致性要求
                    - 推荐：1-3m 用于平缓河流，3-5m 用于陡峭河流""",
                )
            with col3:
                min_samples = st.slider(
                    "最小样本数",
                    3,
                    20,
                    5,
                    1,
                    help="""形成有效聚类所需的最小点数。
                    - 较大值：过滤更多噪声，但可能丢失部分真实信号
                    - 较小值：保留更多数据，但可能包含噪声
                    - 推荐：5-10 用于一般场景""",
                )

            method = "dbscan"
            method_params = {
                "eps_along": eps_along,
                "eps_height": eps_height,
                "min_samples": min_samples,
            }

        elif "滑动中位数" in method_choice:
            st.info(
                """
            **滑动中位数过滤**
            
            - 核心思想：使用滑动窗口计算局部统计，移除异常值
            - 适用场景：数据分布相对连续，存在局部离群点
            - 优势：能够适应水位的缓慢变化，保留趋势信息
            """
            )

            col1, col2 = st.columns(2)
            with col1:
                window_size = st.slider(
                    "滑动窗口大小",
                    10,
                    200,
                    50,
                    10,
                    help="""用于计算局部统计的数据点数量。
                    - 较大值：平滑效果更强，适应缓慢变化的趋势
                    - 较小值：更敏感，能捕捉局部细节
                    - 推荐：50-100 用于河流数据
                    - 注意：窗口越大，边界点处理越保守""",
                )
            with col2:
                threshold_std = st.slider(
                    "标准差阈值倍数",
                    1.0,
                    5.0,
                    2.0,
                    0.5,
                    help="""决定数据点与局部中位数的最大允许偏差。
                    - 较大值：保留更多数据，容忍较大波动
                    - 较小值：更严格的过滤，只保留接近中位数的点
                    - 推荐：2-3倍标准差涵盖约95%-99.7%的正常数据""",
                )

            method = "sliding_median"
            method_params = {"window_size": window_size, "threshold_std": threshold_std}

        else:  # 百分位数过滤
            st.info(
                """
            **百分位数过滤**
            
            - 核心思想：移除前后极端百分位数的点，保留中间部分
            - 适用场景：数据分布相对稳定，极端值明显
            - 优势：简单直接，计算效率高
            """
            )

            col1, col2 = st.columns(2)
            with col1:
                lower_pct = st.slider(
                    "下限百分位数 (%)",
                    0.0,
                    40.0,
                    25.0,
                    5.0,
                    help="""移除低于此百分位数的所有数据点。
                    - 例如：25% 表示移除最低的25%的点
                    - 用于过滤地面反射等低值噪声
                    - 推荐：10-25% 用于一般场景""",
                )
            with col2:
                upper_pct = st.slider(
                    "上限百分位数 (%)",
                    60.0,
                    100.0,
                    75.0,
                    5.0,
                    help="""移除高于此百分位数的所有数据点。
                    - 例如：75% 表示移除最高的25%的点
                    - 用于过滤云层反射等高值噪声
                    - 推荐：75-90% 用于一般场景
                    - 注意：下限25% + 上限75% = 保留中间50%""",
                )

            if lower_pct >= upper_pct:
                st.error("下限必须小于上限！")
                return

            method = "percentile"
            method_params = {
                "lower_percentile": lower_pct,
                "upper_percentile": upper_pct,
            }

        # 文件选择模式
        st.markdown("---")
        process_mode = st.radio(
            "处理模式", ["批量处理所有文件并合并", "处理单个文件"], horizontal=True
        )

        if process_mode == "处理单个文件":
            selected_file = st.selectbox(
                "选择文件", csv_files, format_func=lambda x: x.name
            )
            selected_files = [selected_file]
        else:
            selected_files = csv_files

        # 开始处理按钮
        if st.button("开始处理数据", type="primary", width="stretch"):
            with st.spinner(f"正在使用 {method_choice} 处理数据..."):
                try:
                    # 批量处理
                    filtered_df, total, kept = batch_process_csv_files(
                        csv_files=selected_files,
                        method=method,
                        method_params=method_params,
                    )

                    if not filtered_df.empty:
                        # 保存结果
                        output_dir = st.session_state.download_dir.parent / "processed"
                        output_dir.mkdir(exist_ok=True)

                        if len(selected_files) > 1:
                            output_filename = f"processed_merged_{method}.csv"
                        else:
                            output_filename = (
                                f"processed_{selected_files[0].stem}_{method}.csv"
                            )

                        output_path = output_dir / output_filename
                        filtered_df.to_csv(output_path, index=False)

                        # 保存到session state（包含统计信息）
                        st.session_state.processed_data = filtered_df
                        st.session_state.data_processed = True
                        st.session_state.processing_stats = {
                            "total_points": total,
                            "kept_points": kept,
                            "retention_rate": kept / total * 100 if total > 0 else 0,
                        }

                        st.rerun()  # 刷新页面显示底部结果

                    else:
                        st.error("处理后没有保留任何数据点，请调整参数后重试")

                except Exception as e:
                    st.error(f"处理失败: {str(e)}")
                    import traceback

                    with st.expander("查看详细错误信息"):
                        st.code(traceback.format_exc())

    else:
        st.error("未找到下载目录信息")

    # 在所有参数设置和处理按钮之后，显示已有的处理结果（如果有）
    if st.session_state.data_processed and st.session_state.processed_data is not None:
        st.markdown("---")
        st.markdown("---")

        # 显示已处理的结果
        filtered_df = st.session_state.processed_data
        stats = calculate_water_level_statistics(filtered_df)

        # 获取保存的处理统计信息
        processing_stats = getattr(st.session_state, "processing_stats", {})
        total_points = processing_stats.get("total_points", len(filtered_df))
        kept_points = processing_stats.get("kept_points", len(filtered_df))
        retention_rate = processing_stats.get("retention_rate", 100.0)

        st.subheader("处理结果")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("原始点数", f"{total_points:,}")
            st.metric("保留点数", f"{kept_points:,}")
        with col2:
            st.metric("保留率", f"{retention_rate:.1f}%")
            st.metric("标准差", f"{stats['std']:.3f} m")
        with col3:
            st.metric("平均水位", f"{stats['mean']:.3f} m")
            st.caption(f"完整数值: {stats['mean']:.6f} m")

        # 下载按钮
        csv_data = filtered_df.to_csv(index=False)
        st.download_button(
            label="下载处理后的数据",
            data=csv_data,
            file_name="processed_data.csv",
            mime="text/csv",
            use_container_width=True,
        )
