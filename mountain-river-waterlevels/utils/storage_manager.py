"""
临时存储管理模块 - 简化版
仅管理当前会话的数据存储
"""

import streamlit as st
from pathlib import Path
import shutil
from datetime import datetime


class StorageManager:
    """简化的存储管理器 - 仅管理当前会话数据"""

    def __init__(self, base_dir: str = "temp_data"):
        """
        初始化存储管理器

        Args:
            base_dir: 基础临时目录名称
        """
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

        # 为当前会话创建唯一目录
        if "session_id" not in st.session_state:
            st.session_state.session_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")

        self.session_dir = self.base_dir / st.session_state.session_id
        self.session_dir.mkdir(parents=True, exist_ok=True)

    def get_data_dir(self, data_type: str) -> Path:
        """
        获取特定数据类型的目录

        Args:
            data_type: 数据类型 (h5, csv, processed)

        Returns:
            Path: 数据目录路径
        """
        data_dir = self.session_dir / data_type
        data_dir.mkdir(parents=True, exist_ok=True)
        return data_dir

    def clear_session_data(self) -> bool:
        """
        清理当前会话的所有数据

        Returns:
            bool: 清理是否成功
        """
        try:
            if self.session_dir.exists():
                shutil.rmtree(self.session_dir)
                self.session_dir.mkdir(parents=True, exist_ok=True)
            return True
        except Exception as e:
            st.error(f"清理数据失败: {str(e)}")
            return False

    def get_session_size(self) -> float:
        """
        获取当前会话数据大小（MB）

        Returns:
            float: 数据大小（MB）
        """
        try:
            total_size = sum(
                f.stat().st_size for f in self.session_dir.rglob("*") if f.is_file()
            )
            return total_size / (1024 * 1024)
        except:
            return 0.0


def render_storage_panel():
    """渲染存储管理面板 - 仅显示数据量"""
    storage = StorageManager()

    # 显示当前会话数据大小
    session_size = storage.get_session_size()
    st.metric("当前数据量", f"{session_size:.1f} MB")

    st.caption("提示：数据在当前会话中保存，关闭浏览器后自动清理")


def auto_cleanup_on_startup():
    """启动时清理（简化版 - 不执行任何操作）"""
    pass  # 不需要自动清理，数据仅在当前会话中
