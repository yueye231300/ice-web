"""
H5 文件处理模块
将 ICESat-2 H5 文件转换为 CSV
"""

import h5py
import pandas as pd
import numpy as np
from pathlib import Path
from typing import List, Optional
import streamlit as st
from utils.storage_manager import StorageManager


# 默认的子组
SUBGROUPS_DEFAULT = ["gt1l", "gt1r", "gt2l", "gt2r", "gt3l", "gt3r"]


def extract_h5_to_csv(
    h5_file: Path, output_dir: Path, subgroups: Optional[List[str]] = None
) -> Optional[Path]:
    """
    将单个 H5 文件转换为 CSV

    Args:
        h5_file: H5 文件路径
        output_dir: 输出目录
        subgroups: 要提取的子组列表

    Returns:
        Optional[Path]: 输出的 CSV 文件路径
    """
    if subgroups is None:
        subgroups = SUBGROUPS_DEFAULT

    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / f"{h5_file.stem}.csv"

    # 字段映射
    field_map = {
        "lat": "segment_lat",
        "lon": "segment_lon",
        "ht_ortho": "ht_ortho",
        "delta_time": "delta_time",
        "rgt": "rgt",
        "cycle_number": "cycle_number",
        "qf_bckgrd": "qf_bckgrd",
        "qf_bias_em": "qf_bias_em",
        "qf_bias_fit": "qf_bias_fit",
        "significant_wave_ht": "significant_wave_ht",
        "stdev_water_surf": "stdev_water_surf",
        "segment_fpb_correction": "segment_fpb_correction",
        "waterbody_type": "inland_water_body_type",
        "cloud_flag": "cloud_flag_asr_atl09",
        "ht_water_surf": "ht_water_surf",
    }

    def _ds_to_col(ds, n: int, col_name: str) -> np.ndarray:
        """将 H5 dataset 转为长度为 n 的 1D array"""
        if ds is None:
            return np.full(n, np.nan, dtype=float)

        arr = np.asarray(ds[()])

        # 标量：广播
        if arr.ndim == 0:
            try:
                val = float(arr)
                return np.full(n, val)
            except Exception:
                return np.array([arr] * n, dtype=object)

        # 数组：拉平为 1D
        arr = arr.reshape(-1)
        m = len(arr)

        if m == n:
            return arr
        if m == 1:
            return np.full(n, arr[0])

        # 不一致：截断/补 NaN
        out = np.full(n, np.nan, dtype=float)
        k = min(n, m)
        try:
            out[:k] = arr[:k].astype(float)
            return out
        except Exception:
            out_obj = np.array([None] * n, dtype=object)
            out_obj[:k] = arr[:k]
            return out_obj

    all_dfs = []

    try:
        with h5py.File(h5_file, "r") as data:
            for subgroup in subgroups:
                subgroup_path = f"{subgroup}/"
                if subgroup_path not in data:
                    continue

                # 确定基准长度
                n = None
                lat_ds = data.get(f"{subgroup_path}/{field_map['lat']}")
                if lat_ds is not None:
                    try:
                        n = int(np.asarray(lat_ds[()]).reshape(-1).shape[0])
                    except Exception:
                        n = None

                if n is None or n <= 0:
                    # 找任意一个存在的字段当基准
                    for col, key in field_map.items():
                        ds = data.get(f"{subgroup_path}/{key}")
                        if ds is None:
                            continue
                        try:
                            arr = np.asarray(ds[()])
                            if arr.ndim == 0:
                                continue
                            n = int(arr.reshape(-1).shape[0])
                            break
                        except Exception:
                            continue

                if n is None or n <= 0:
                    continue

                # 逐字段构造列
                df_dict = {"subgroup": [subgroup] * n}
                for col, key in field_map.items():
                    ds = data.get(f"{subgroup_path}/{key}")
                    df_dict[col] = _ds_to_col(ds, n, col)

                df = pd.DataFrame(df_dict)
                all_dfs.append(df)

        if not all_dfs:
            return None

        combined = pd.concat(all_dfs, ignore_index=True)
        combined.to_csv(csv_path, index=False, na_rep="")

        return csv_path

    except Exception as e:
        st.error(f"处理 {h5_file.name} 失败: {str(e)}")
        return None


def batch_h5_to_csv(
    input_dir: Path, output_dir: Optional[Path] = None, pattern: str = "*_ATL13*.h5"
) -> int:
    """
    批量转换 H5 文件为 CSV

    Args:
        input_dir: 输入目录
        output_dir: 输出目录（如果为None，使用临时存储）
        pattern: 文件匹配模式

    Returns:
        int: 成功转换的文件数
    """
    h5_files = list(input_dir.glob(pattern))

    if not h5_files:
        st.error("未找到 H5 文件")
        st.info("请确保已成功下载数据")
        return 0

    # 如果未指定输出目录，使用临时存储
    if output_dir is None:
        storage = StorageManager()
        output_dir = storage.get_data_dir("csv")

    st.info(f"找到 {len(h5_files)} 个文件，开始转换...")

    success_count = 0
    progress_bar = st.progress(0)
    status_text = st.empty()

    for i, h5_file in enumerate(h5_files):
        status_text.text(f"正在处理: {h5_file.name} ({i+1}/{len(h5_files)})")

        result = extract_h5_to_csv(h5_file, output_dir)
        if result:
            success_count += 1

        progress_bar.progress((i + 1) / len(h5_files))

    status_text.empty()
    progress_bar.empty()

    if success_count > 0:
        st.success(f"成功转换 {success_count}/{len(h5_files)} 个文件")
    else:
        st.error("转换失败")

    return success_count
