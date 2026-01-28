# 🏔️ 高山河流虚拟水位测量系统 

## 项目概述

构建了一个以Streamlit为前端的Web应用，配合icepyx 可以实现对于缺乏水文测站的高山河流区域的水位进行初步的计算和统计。该系统通过下载NASA ICESat-2 卫星数据，并结合多种异常值过滤方法，最终生成虚拟测站的水位统计结果。

## 📁 项目结构

```
mountain-river-waterlevels/
├──应用核心
│   ├── app.py                      # Streamlit 主应用
│   └── utils/                      # 工具模块包
│       ├── __init__.py
│       ├── area_selector.py        # 区域选择工具
│       ├── icesat2_downloader.py   # ICESat-2 下载器
│       ├── h5_processor.py         # H5 文件处理
│       └── water_level_viz.py      # 水位可视化
│
├── 配置文件
│   ├── .streamlit/
│   │   ├── config.toml             # Streamlit 配置
│   ├── requirements.txt            # Python 依赖
│   └── .gitignore                  # Git 忽略规则
│
├── 文档
│   ├── README.md                   # 项目说明
└── 数据目录（运行时创建）
    └── temp_data/                 # 临时数据存储
        ├── h5/                     # ICESat-2 原始文件
        ├── csv/                    # 转换后的 CSV
        └── processed/              # 过滤后的数据
```

## ✨ 实现的功能

### 1. 区域选择（3种方式）

✅ **坐标 + 缓冲区**
- 输入中心点经纬度
- 自定义缓冲区半径
- 自动创建圆形区域

✅ **边界框（BBox）**
- 输入矩形范围
- 最小/最大经纬度
- 灵活定义研究区

✅ **Shapefile 上传**
- 支持 .shp 文件
- 自动坐标系转换
- 复杂边界支持

✅ **交互式地图选择**
- Folium 地图界面
- 鼠标绘制多边形
- 实时显示选区

### 2. 数据下载

✅ **ICESat-2 数据查询**
- 使用 icepyx 库
- 自定义时间范围
- 产品类型选择（ATL13/ATL08/ATL06）

✅ **自动下载**
- 重试机制（网络不稳定）
- 断点续传支持
- 进度实时反馈

### 3. 数据处理

✅ **H5 转 CSV**
- 批量文件处理
- 字段自动映射
- 多子组合并（gt1l-gt3r）
- 缺失值智能处理

✅ **水位过滤算法**
- DBSCAN 空间聚类
- 滑动中位数滤波
- 百分位数异常值剔除

### 4. 可视化展示

✅ **虚拟测站地图**
- Folium 交互地图
- 测站聚合算法
- 分级标记（观测次数）
- 弹窗详情

✅ **统计图表**
- 水位分布直方图
- 过滤统计饼图
- Plotly 交互图表

### 5. 数据导出

✅ **CSV 下载**
- 过滤后的完整数据
- 时间戳文件名
- 一键下载

## 🔧 技术栈

### 后端处理
- **Python 3.8+**: 核心语言
- **icepyx**: ICESat-2 数据访问
- **h5py**: HDF5 文件处理
- **pandas**: 数据处理
- **numpy**: 数值计算

### 地理处理
- **geopandas**: 矢量数据处理
- **shapely**: 几何操作
- **pyproj**: 坐标系转换

### 可视化
- **Streamlit**: Web 应用框架
- **Folium**: 交互式地图
- **Plotly**: 交互式图表
- **streamlit-folium**: Folium + Streamlit 集成

## 🔮 未来扩展方向
### 长期愿景
- [ ] 机器学习增强
- [ ] 实时数据推送
- [ ] API 服务
- [ ] 移动端应用


### 贡献代码
欢迎提交 Pull Request！

## 🙏 致谢

感谢以下开源项目和服务：
- NASA ICESat-2 Mission
- ESA Copernicus Programme
- Streamlit
- icepyx


