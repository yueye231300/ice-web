"""
ICESat-2 数据下载模块
"""

import icepyx as ipx
import earthaccess
import streamlit as st
from pathlib import Path
from typing import List, Optional
import time
from utils.storage_manager import StorageManager


def authenticate_earthdata() -> bool:
    """
    使用 Streamlit secrets 配置 NASA Earthdata 认证

    Returns:
        bool: 认证是否成功
    """
    try:
        # 设置环境变量（必须在调用 login 之前）
        if "earthdata_username" in st.secrets and "earthdata_password" in st.secrets:
            import os

            os.environ["EARTHDATA_USERNAME"] = st.secrets["earthdata_username"]
            os.environ["EARTHDATA_PASSWORD"] = st.secrets["earthdata_password"]

        # 尝试登录认证
        auth = earthaccess.login(strategy="environment", persist=True)

        if auth:
            return True
        else:
            st.warning("⚠️ 认证未成功，但将尝试继续")
            return False

    except Exception as e:
        st.error("NASA Earthdata 认证失败")
        with st.expander("查看详细错误信息"):
            st.code(str(e))
        st.info(
            "请在 .streamlit/secrets.toml 中配置 earthdata_username 和 earthdata_password"
        )
        return False


def download_icesat2_data(
    bbox: List[float],
    start_date: str,
    end_date: str,
    output_dir: Path,
    product: str = "ATL13",
    version: str = "007",
    max_retries: int = 3,
    retry_delay: int = 30,
) -> bool:
    """
    下载 ICESat-2 数据

    Args:
        bbox: 边界框 [min_lon, min_lat, max_lon, max_lat]
        start_date: 开始日期 (YYYY-MM-DD)
        end_date: 结束日期 (YYYY-MM-DD)
        output_dir: 输出目录
        product: 产品类型，默认 ATL13
        version: 版本号，默认 007
        max_retries: 最大重试次数
        retry_delay: 重试延迟（秒）

    Returns:
        bool: 下载是否成功
    """
    # 先进行 NASA Earthdata 认证
    if not authenticate_earthdata():
        return False

    try:
        # 使用临时存储管理器
        storage = StorageManager()
        output_dir = storage.get_data_dir("h5")

        st.info(f"查询 ICESat-2 {product} 数据...")
        st.write(f"- 时间范围: {start_date} 至 {end_date}")
        st.write(f"- 空间范围: {bbox}")

        # 创建查询
        query = ipx.Query(
            product=product,
            spatial_extent=bbox,
            date_range=[start_date, end_date],
            start_time="00:00:00",
            end_time="23:59:59",
            version=version,
        )

        # 获取可用数据数量
        try:
            granules = query.avail_granules()
            num_granules = len(granules)
            st.success(f"找到 {num_granules} 个数据文件")
        except Exception as e:
            st.warning("⚠️ 无法获取数据文件数量，但将继续尝试下载")
            num_granules = 0

        # 下载数据（带重试机制）
        for attempt in range(max_retries):
            try:
                st.info(f"开始下载数据 (尝试 {attempt + 1}/{max_retries})...")

                # 创建进度条
                progress_bar = st.progress(0)
                status_text = st.empty()

                # 订购数据
                status_text.text("正在订购数据...")
                progress_bar.progress(0.2)

                # 确保 earthaccess 已登录（icepyx 会自动使用）
                import earthaccess

                earthaccess.login(strategy="environment")

                # 创建订单
                order = query.order_granules(subset=True)

                # 下载数据
                status_text.text(f"正在下载数据...")
                progress_bar.progress(0.5)

                # 执行下载
                result = order.download_granules(str(output_dir))

                progress_bar.progress(0.9)

                # 查找所有下载的 H5 文件（包括子目录）
                downloaded_files = list(output_dir.rglob("*.h5"))

                if downloaded_files:
                    # 如果文件在子目录中，移动到主目录
                    moved_files = []
                    for f in downloaded_files:
                        if f.parent != output_dir:
                            target = output_dir / f.name
                            f.rename(target)
                            moved_files.append(target)
                        else:
                            moved_files.append(f)

                    progress_bar.progress(1.0)
                    status_text.text("下载完成！")

                    st.success(f"数据下载完成！共 {len(moved_files)} 个文件")

                    with st.expander("查看下载的文件"):
                        for f in moved_files:
                            st.write(
                                f"• {f.name} ({f.stat().st_size / 1024 / 1024:.2f} MB)"
                            )

                    return True
                else:
                    st.warning("未找到 .h5 文件，请检查下载是否成功")
                    return False

            except Exception as e:
                if attempt < max_retries - 1:
                    st.warning(f" 网络连接问题，{retry_delay} 秒后自动重试...")
                    time.sleep(retry_delay)
                else:
                    st.error(" 下载失败，请检查网络连接后重试")
                    with st.expander("查看详细错误信息"):
                        st.code(str(e))
                    return False

        return False

    except Exception as e:
        st.error(" 查询失败，请检查网络连接")
        with st.expander("查看详细错误信息"):
            st.code(str(e))
        return False


def list_downloaded_files(directory: Path, pattern: str = "*_ATL13*.h5") -> List[Path]:
    """
    列出已下载的文件

    Args:
        directory: 目录路径
        pattern: 文件匹配模式

    Returns:
        List[Path]: 文件路径列表
    """
    if not directory.exists():
        return []
    return list(directory.glob(pattern))


def render_download_interface():
    """
    渲染下载界面
    """
    st.subheader("下载 ICESat-2 数据")

    # 检查是否有选中的区域
    if st.session_state.current_bbox is None:
        st.warning("请先在 '区域选择' 中定义研究区域")
        return

    st.info(f"当前选中区域: {st.session_state.current_bbox}")

    # 时间选择
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("开始日期", value=None)
    with col2:
        end_date = st.date_input("结束日期", value=None)

    # 产品选择
    col3, col4 = st.columns(2)
    with col3:
        product = st.selectbox("产品类型", ["ATL13", "ATL08", "ATL06"], index=0)
    with col4:
        version = st.selectbox("版本", ["007", "006", "005"], index=0)

    # 下载按钮
    if st.button("开始下载", type="primary"):
        if start_date is None or end_date is None:
            st.error("请选择时间范围")
            return

        if start_date > end_date:
            st.error("开始日期不能晚于结束日期")
            return

        with st.spinner("正在下载数据，请稍候..."):
            # 使用临时存储管理器
            storage = StorageManager()
            output_dir = storage.get_data_dir("h5")

            success = download_icesat2_data(
                bbox=st.session_state.current_bbox,
                start_date=start_date.strftime("%Y-%m-%d"),
                end_date=end_date.strftime("%Y-%m-%d"),
                output_dir=output_dir,
                product=product,
                version=version,
            )

            if success:
                st.session_state.data_downloaded = True
                st.session_state.download_dir = output_dir
