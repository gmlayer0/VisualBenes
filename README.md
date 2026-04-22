# 多级互连网络可视化程序

一个基于 PyQt5 的通用多级开关网络可视化程序，支持 Benes 网络和通用模式。

## 功能特性

### 通用多级开关网络框架
- 可配置的级数和每级开关数量
- 直连模式拓扑
- 点击开关切换状态（绿色=直通，橙色=交叉）
- 数据流着色显示（使用 Tableau 10 色板）
- 控制位加载/导出功能
- 自适应布局

### Benes 网络专用拓扑
- 支持网络规模 N = 2, 4, 8, 16, 32, 64
- 递归构建的完美洗牌/逆洗牌连接
- 自动计算级数和每级开关数

## 安装

```bash
pip install -r requirements.txt
```

## 运行

```bash
python visual_benes.py
```

## 使用说明

### Benes 模式
1. 在"网络类型"下拉框中选择 "Benes 网络"
2. 在"网络规模"中选择 N 的值（2, 4, 8, 16, 32, 64）
3. 点击开关可以切换其状态
4. 观察数据流从输入到输出的传播

### 通用模式
1. 在"网络类型"下拉框中选择 "通用模式"
2. 设置所需的级数和每级开关数量
3. 程序自动创建直连模式的拓扑

### 控制位操作
- **导出**：将当前所有开关状态导出为二进制字符串
- **加载**：从二进制字符串加载开关状态（顺序：第0级第0个开关为最低位）

### 快捷操作
- **随机状态**：随机设置所有开关的状态
- **重置为直通**：将所有开关设置为直通状态（0）

## 程序结构

- `ColorManager`: 颜色管理，使用 Tableau 10 色板
- `NetworkTopology`: 网络拓扑，管理开关、端口和连接
- `LayoutCalculator`: 布局计算
- `DataFlowPropagator`: 数据流传播
- `BenesTopologyBuilder`: Benes 网络拓扑生成器
- `GenericTopologyBuilder`: 通用网络拓扑生成器
- `SwitchGraphicsItem`: 开关图形项
- `ConnectionGraphicsItem`: 连接线图形项
- `NetworkGraphicsView`: 网络图形视图
- `MainWindow`: 主窗口
