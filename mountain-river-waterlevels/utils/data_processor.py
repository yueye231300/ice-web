"""
ICESat-2 数据处理模块
包含多种水位提取和噪声过滤方法
"""

import pandas as pd
import numpy as np
from sklearn.cluster import DBSCAN
from scipy import stats
import streamlit as st
from pathlib import Path
from typing import Tuple, Optional, List


def method_dbscan_elliptical(
    df: pd.DataFrame,
    eps_along: float = 50.0,
    eps_height: float = 2.0,
    min_samples: int = 5,
) -> Tuple[pd.DataFrame, int, int]:
    """
    基于椭圆邻域的DBSCAN聚类方法

    核心思想：水面光子在空间上是高密度聚集的，而噪声光子是稀疏分布的。
    针对ATL13数据的条带状特征（沿轨方向长，高程方向窄），使用椭圆邻域。

    Args:
        df: 包含经纬度和水位的DataFrame
        eps_along: 沿轨方向的邻域半径（米），默认50米
        eps_height: 高程方向的邻域半径（米），默认2米
        min_samples: 最小样本数，默认5

    Returns:
        Tuple[pd.DataFrame, int, int]: (过滤后的数据, 原始点数, 保留点数)
    """
    if df.empty or "ht_water_surf" not in df.columns:
        return pd.DataFrame(), 0, 0

    total = len(df)

    # 准备数据：将经纬度转换为距离（简化版，使用度数差）
    # 实际应用中可以使用更精确的地理距离计算
    df_work = df.copy()

    # 计算沿轨距离（假设数据按时间排序）
    if "delta_time" in df_work.columns:
        df_work = df_work.sort_values("delta_time")

    # 归一化坐标以创建椭圆邻域
    # 将沿轨方向和高程方向缩放到相同的尺度
    if len(df_work) < min_samples:
        return pd.DataFrame(), total, 0

    # 计算相对距离
    df_work["along_track"] = np.arange(len(df_work))

    # 构建特征矩阵：沿轨距离和高程
    # 通过缩放因子创建椭圆邻域效果
    scale_factor = eps_along / eps_height
    X = np.column_stack(
        [df_work["along_track"], df_work["ht_water_surf"] * scale_factor]
    )

    # DBSCAN聚类
    try:
        db = DBSCAN(eps=eps_along, min_samples=min_samples)
        labels = db.fit_predict(X)

        # 找出最大的聚类（认为是水面）
        unique_labels = set(labels)
        unique_labels.discard(-1)  # 移除噪声标签

        if not unique_labels:
            st.warning("DBSCAN未找到有效聚类，所有点被标记为噪声")
            return pd.DataFrame(), total, 0

        # 选择最大的聚类
        cluster_sizes = {label: np.sum(labels == label) for label in unique_labels}
        main_cluster = max(cluster_sizes, key=cluster_sizes.get)

        # 过滤数据
        df_filtered = df_work[labels == main_cluster].copy()
        df_filtered = df_filtered.drop(columns=["along_track"], errors="ignore")

        kept = len(df_filtered)

        return df_filtered, total, kept

    except Exception as e:
        st.error(f"DBSCAN处理失败: {str(e)}")
        return pd.DataFrame(), total, 0


def method_sliding_median(
    df: pd.DataFrame, window_size: int = 50, threshold_std: float = 2.0
) -> Tuple[pd.DataFrame, int, int]:
    """
    滑动中位数方法

    核心思想：使用滑动窗口计算局部中位数和标准差，
    移除偏离局部中位数超过一定阈值的点。

    Args:
        df: 包含水位数据的DataFrame
        window_size: 滑动窗口大小，默认50个点
        threshold_std: 标准差阈值倍数，默认2.0

    Returns:
        Tuple[pd.DataFrame, int, int]: (过滤后的数据, 原始点数, 保留点数)
    """
    if df.empty or "ht_water_surf" not in df.columns:
        return pd.DataFrame(), 0, 0

    total = len(df)
    df_work = df.copy()

    # 按时间或位置排序
    if "delta_time" in df_work.columns:
        df_work = df_work.sort_values("delta_time")

    # 计算滑动中位数和标准差
    heights = df_work["ht_water_surf"].values

    if len(heights) < window_size:
        # 数据点太少，使用全局统计
        median = np.median(heights)
        std = np.std(heights)
        mask = np.abs(heights - median) <= threshold_std * std
        df_filtered = df_work[mask].copy()
        return df_filtered, total, len(df_filtered)

    # 计算滑动统计
    rolling_median = (
        pd.Series(heights)
        .rolling(window=window_size, center=True, min_periods=1)
        .median()
    )

    rolling_std = (
        pd.Series(heights).rolling(window=window_size, center=True, min_periods=1).std()
    )

    # 过滤：保留在中位数±threshold_std*std范围内的点
    deviation = np.abs(heights - rolling_median)
    threshold = threshold_std * rolling_std
    mask = deviation <= threshold

    df_filtered = df_work[mask].copy()
    kept = len(df_filtered)

    return df_filtered, total, kept


def method_middle_percentile(
    df: pd.DataFrame, lower_percentile: float = 25.0, upper_percentile: float = 75.0
) -> Tuple[pd.DataFrame, int, int]:
    """
    百分位数过滤方法（去除前后极端值）

    核心思想：移除前后一定百分比的极端值，只保留中间部分数据。
    适用于数据分布相对稳定的情况。

    Args:
        df: 包含水位数据的DataFrame
        lower_percentile: 下限百分位数，默认25
        upper_percentile: 上限百分位数，默认75

    Returns:
        Tuple[pd.DataFrame, int, int]: (过滤后的数据, 原始点数, 保留点数)
    """
    if df.empty or "ht_water_surf" not in df.columns:
        return pd.DataFrame(), 0, 0

    total = len(df)

    # 计算百分位数
    heights = df["ht_water_surf"].dropna()
    q_lower = np.percentile(heights, lower_percentile)
    q_upper = np.percentile(heights, upper_percentile)

    # 过滤
    df_filtered = df[
        (df["ht_water_surf"] >= q_lower) & (df["ht_water_surf"] <= q_upper)
    ].copy()

    kept = len(df_filtered)

    return df_filtered, total, kept


def batch_process_csv_files(
    csv_files: List[Path], method: str = "dbscan", method_params: dict = None
) -> Tuple[pd.DataFrame, int, int]:
    """
    批量处理CSV文件并合并结果

    Args:
        csv_files: CSV文件路径列表
        method: 处理方法 ("dbscan", "sliding_median", "percentile")
        method_params: 方法参数字典

    Returns:
        Tuple[pd.DataFrame, int, int]: (合并后过滤的数据, 总原始点数, 总保留点数)
    """
    if method_params is None:
        method_params = {}

    all_filtered_data = []
    total_points = 0
    total_kept = 0

    # 简化显示，只显示进度条
    file_progress = st.progress(0)
    status_text = st.empty()

    for file_idx, csv_file in enumerate(csv_files):
        status_text.text(f"正在处理: {csv_file.name} ({file_idx + 1}/{len(csv_files)})")

        try:
            df = pd.read_csv(csv_file)

            if df.empty:
                continue

            # 选择处理方法
            if method == "dbscan":
                filtered_df, file_total, file_kept = method_dbscan_elliptical(
                    df, **method_params
                )
            elif method == "sliding_median":
                filtered_df, file_total, file_kept = method_sliding_median(
                    df, **method_params
                )
            elif method == "percentile":
                filtered_df, file_total, file_kept = method_middle_percentile(
                    df, **method_params
                )
            else:
                continue

            if not filtered_df.empty:
                all_filtered_data.append(filtered_df)
                total_points += file_total
                total_kept += file_kept
            else:
                total_points += file_total

        except Exception as e:
            # 静默失败，不显示错误
            pass

        file_progress.progress((file_idx + 1) / len(csv_files))

    # 清除临时显示
    status_text.empty()
    file_progress.empty()

    # 合并所有过滤后的数据
    if all_filtered_data:
        merged_df = pd.concat(all_filtered_data, ignore_index=True)
        st.success(f"✅ 处理完成！")
    else:
        merged_df = pd.DataFrame()
        st.warning("没有数据被保留")

    return merged_df, total_points, total_kept


def calculate_water_level_statistics(df: pd.DataFrame) -> dict:
    """
    计算水位统计信息

    Args:
        df: 包含水位数据的DataFrame

    Returns:
        dict: 统计信息字典
    """
    if df.empty or "ht_water_surf" not in df.columns:
        return {}

    heights = df["ht_water_surf"].dropna()

    stats = {
        "count": len(heights),
        "mean": heights.mean(),
        "median": heights.median(),
        "std": heights.std(),
        "min": heights.min(),
        "max": heights.max(),
        "q25": heights.quantile(0.25),
        "q75": heights.quantile(0.75),
        "iqr": heights.quantile(0.75) - heights.quantile(0.25),
    }

    # 使用中间50%计算的均值
    if len(heights) >= 4:
        q25_idx = int(len(heights) * 0.25)
        q75_idx = int(len(heights) * 0.75)
        sorted_heights = heights.sort_values()
        middle_heights = sorted_heights.iloc[q25_idx:q75_idx]
        stats["middle_50_mean"] = middle_heights.mean()
    else:
        stats["middle_50_mean"] = stats["mean"]

    return stats
