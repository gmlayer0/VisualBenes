#!/usr/bin/env python3
"""
多级互连网络可视化程序
包含通用多级开关网络框架和 Benes 网络专用拓扑实现
"""

import math
import sys
import random
from typing import List, Tuple, Dict, Optional, Callable
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSpinBox, QPushButton, QLabel, QComboBox, QTextEdit, QGroupBox,
    QFormLayout, QGraphicsItem, QGraphicsEllipseItem, QGraphicsLineItem,
    QGraphicsTextItem, QGraphicsScene, QGraphicsView, QGraphicsRectItem
)
from PyQt5.QtCore import Qt, QPointF, QRectF, QLineF, QRect
from PyQt5.QtGui import QColor, QPen, QBrush, QPainter, QFont, QPainterPath, QRadialGradient, QLinearGradient


# =============================================================================
# 颜色管理
# =============================================================================

class ColorManager:
    """颜色管理器，为输入端口分配高区分度的固定颜色"""

    # 扩展到 16 种高区分度颜色
    COLORS_16 = [
        QColor(31, 119, 180),   # 蓝色
        QColor(255, 127, 14),   # 橙色
        QColor(44, 160, 44),    # 绿色
        QColor(214, 39, 40),    # 红色
        QColor(148, 103, 189),  # 紫色
        QColor(140, 86, 75),    # 棕色
        QColor(227, 119, 194),  # 粉色
        QColor(127, 127, 127),  # 灰色
        QColor(188, 189, 34),   # 橄榄色
        QColor(23, 190, 207),   # 青色
        QColor(174, 199, 232),  # 浅蓝
        QColor(255, 187, 120),  # 浅橙
        QColor(152, 223, 138),  # 浅绿
        QColor(255, 152, 150),  # 浅红
        QColor(197, 176, 213),  # 浅紫
        QColor(196, 156, 148),  # 浅棕
    ]

    @classmethod
    def get_color(cls, index: int, total: int) -> QColor:
        """
        获取指定索引的颜色

        Args:
            index: 输入端口索引 (0-based)
            total: 总输入端口数量

        Returns:
            对应的 QColor
        """
        if index < 0:
            return QColor(180, 180, 180)  # 灰色表示未使用

        base_idx = index % len(cls.COLORS_16)
        color = cls.COLORS_16[base_idx]

        # 如果超出基础色板数量，通过调整亮度生成新颜色
        if index >= len(cls.COLORS_16):
            cycle = index // len(cls.COLORS_16)
            factor = 1.0 - (cycle * 0.1)  # 每次循环降低亮度
            factor = max(factor, 0.5)  # 最低亮度限制

            h, s, v, a = color.getHsv()
            v = int(v * factor)
            color = QColor.fromHsv(h, s, v, a)

        return color


# =============================================================================
# 拓扑定义
# =============================================================================

class Endpoint:
    """端点类，表示开关或端口的一个输入/输出端点"""

    def __init__(self, owner: object, port_type: str, port_idx: int):
        """
        Args:
            owner: 拥有此端点的对象（SwitchNode 或 Port）
            port_type: "input" 或 "output"
            port_idx: 端口索引 (0 或 1 对于开关，0..N-1 对于端口)
        """
        self.owner = owner
        self.port_type = port_type
        self.port_idx = port_idx
        self.x: float = 0.0
        self.y: float = 0.0


class Port:
    """外部端口类（输入或输出）"""

    def __init__(self, port_idx: int, is_input: bool):
        self.port_idx = port_idx
        self.is_input = is_input
        self.endpoint = Endpoint(self, "output" if is_input else "input", port_idx)
        self.x: float = 0.0
        self.y: float = 0.0
        self.radius: float = 14.0

    def endpoints(self) -> List[Endpoint]:
        return [self.endpoint]


class SwitchNode:
    """2×2 开关节点类"""

    def __init__(self, stage_idx: int, switch_idx: int):
        self.stage_idx = stage_idx
        self.switch_idx = switch_idx
        self.state: int = 0  # 0=直通, 1=交叉
        self.x: float = 0.0
        self.y: float = 0.0
        self.width: float = 50.0
        self.height: float = 40.0

        # 输入端点（左侧）
        self.inputs = [
            Endpoint(self, "input", 0),
            Endpoint(self, "input", 1)
        ]
        # 输出端点（右侧）
        self.outputs = [
            Endpoint(self, "output", 0),
            Endpoint(self, "output", 1)
        ]

    def endpoints(self) -> List[Endpoint]:
        return self.inputs + self.outputs

    def toggle(self):
        """切换开关状态"""
        self.state = 1 - self.state

    def get_output_for_input(self, input_idx: int) -> Tuple[int, Endpoint]:
        """
        根据开关状态，获取输入端口对应的输出端口

        Args:
            input_idx: 输入端口索引 (0 或 1)

        Returns:
            (output_idx, output_endpoint)
        """
        if self.state == 0:  # 直通
            output_idx = input_idx
        else:  # 交叉
            output_idx = 1 - input_idx
        return output_idx, self.outputs[output_idx]


class Connection:
    """连接类，表示两个端点之间的连线"""

    def __init__(self, src: Endpoint, dst: Endpoint):
        self.src = src
        self.dst = dst
        self.data_source: int = -1  # 承载的数据来源输入编号，-1 表示未使用


class NetworkTopology:
    """网络拓扑类，管理所有开关、端口和连接"""

    def __init__(self):
        self.input_ports: List[Port] = []
        self.output_ports: List[Port] = []
        self.stages: List[List[SwitchNode]] = []  # 每级的开关列表
        self.connections: List[Connection] = []

    def clear(self):
        """清空拓扑"""
        self.input_ports = []
        self.output_ports = []
        self.stages = []
        self.connections = []

    def add_stage(self, switches: List[SwitchNode]):
        """添加一级开关"""
        self.stages.append(switches)

    def add_connection(self, src: Endpoint, dst: Endpoint):
        """添加连接"""
        self.connections.append(Connection(src, dst))

    def all_switches(self) -> List[SwitchNode]:
        """获取所有开关，按从低地址到高地址的顺序"""
        switches = []
        for stage in self.stages:
            switches.extend(stage)
        return switches

    def switch_count(self) -> int:
        """获取开关总数"""
        return sum(len(stage) for stage in self.stages)


# =============================================================================
# 布局计算
# =============================================================================

class LayoutCalculator:
    """布局计算器，负责计算所有元素的坐标"""

    def __init__(self, margin: float = 40.0):
        self.margin = margin

    def calculate(self, topology: NetworkTopology, width: float, height: float):
        """
        计算拓扑中所有元素的坐标

        Args:
            topology: 网络拓扑
            width: 可用宽度
            height: 可用高度
        """
        if not topology.stages:
            return

        num_stages = len(topology.stages)
        num_inputs = len(topology.input_ports)
        num_outputs = len(topology.output_ports)

        # 计算需要的最大垂直元素数量
        max_vertical = max(num_inputs, num_outputs)
        for stage in topology.stages:
            max_vertical = max(max_vertical, len(stage) * 2)

        # 计算可用区域（增加边距防止溢出）
        avail_width = max(width - 2 * self.margin, 200)
        avail_height = max(height - 2 * self.margin, 200)

        # 动态计算间距，确保不溢出
        min_spacing = 40.0
        vertical_spacing = avail_height / (max_vertical + 1)
        vertical_spacing = max(vertical_spacing, min_spacing)

        # 计算级间距
        stage_x = []
        if num_stages > 0:
            stage_step = avail_width / (num_stages + 1)
            stage_step = max(stage_step, 80)
            for i in range(num_stages):
                stage_x.append(self.margin + stage_step * (i + 1))

        # 计算输入端口位置（左侧）
        input_x = self.margin * 0.5
        if num_inputs > 0:
            input_start_y = (height - (num_inputs - 1) * vertical_spacing) / 2
            for i, port in enumerate(topology.input_ports):
                port.y = input_start_y + i * vertical_spacing
                port.x = input_x
                port.endpoint.x = input_x + port.radius + 5
                port.endpoint.y = port.y

        # 计算输出端口位置（右侧）
        output_x = width - self.margin * 0.5
        if num_outputs > 0:
            output_start_y = (height - (num_outputs - 1) * vertical_spacing) / 2
            for i, port in enumerate(topology.output_ports):
                port.y = output_start_y + i * vertical_spacing
                port.x = output_x
                port.endpoint.x = output_x - port.radius - 5
                port.endpoint.y = port.y

        # 计算每级开关位置
        for stage_idx, stage in enumerate(topology.stages):
            x = stage_x[stage_idx]
            num_switches = len(stage)
            if num_switches > 0:
                switch_start_y = (height - (num_switches * 2 - 1) * vertical_spacing) / 2 + vertical_spacing / 2
                for switch_idx, switch in enumerate(stage):
                    switch.y = switch_start_y + switch_idx * 2 * vertical_spacing
                    switch.x = x

                    # 计算端点坐标
                    half_h = switch.height / 2
                    switch.inputs[0].x = x - switch.width / 2
                    switch.inputs[0].y = switch.y - half_h * 0.6
                    switch.inputs[1].x = x - switch.width / 2
                    switch.inputs[1].y = switch.y + half_h * 0.6

                    switch.outputs[0].x = x + switch.width / 2
                    switch.outputs[0].y = switch.y - half_h * 0.6
                    switch.outputs[1].x = x + switch.width / 2
                    switch.outputs[1].y = switch.y + half_h * 0.6


# =============================================================================
# 数据流传播
# =============================================================================

class DataFlowPropagator:
    """数据流传播器，根据开关状态计算数据流"""

    @staticmethod
    def propagate(topology: NetworkTopology):
        """
        传播数据流：从输入端口开始，根据开关状态追踪数据流向

        Args:
            topology: 网络拓扑
        """
        # 重置所有连接的数据源
        for conn in topology.connections:
            conn.data_source = -1

        # 建立端点到连接的映射
        endpoint_to_out_conn: Dict[Endpoint, Connection] = {}
        endpoint_to_in_conn: Dict[Endpoint, List[Connection]] = {}

        for conn in topology.connections:
            endpoint_to_out_conn[conn.src] = conn
            if conn.dst not in endpoint_to_in_conn:
                endpoint_to_in_conn[conn.dst] = []
            endpoint_to_in_conn[conn.dst].append(conn)

        # 从每个输入端口开始传播
        for input_port in topology.input_ports:
            source_idx = input_port.port_idx
            current_ep = input_port.endpoint

            # 深度优先传播
            stack = [(current_ep, source_idx)]

            while stack:
                ep, data_src = stack.pop()

                # 找到从这个端点出发的连接
                conn = endpoint_to_out_conn.get(ep)
                if conn:
                    conn.data_source = data_src

                    # 检查目标端点的所有者
                    dst_owner = conn.dst.owner

                    if isinstance(dst_owner, SwitchNode):
                        # 目标是开关，根据开关状态决定输出
                        switch = dst_owner
                        input_idx = conn.dst.port_idx
                        output_idx, output_ep = switch.get_output_for_input(input_idx)
                        stack.append((output_ep, data_src))

                    elif isinstance(dst_owner, Port):
                        # 目标是输出端口，传播结束
                        pass


# =============================================================================
# Benes 网络拓扑生成器
# =============================================================================

class BenesTopologyBuilder:
    """Benes 网络拓扑生成器 - 简化的迭代实现"""

    @staticmethod
    def perfect_shuffle(j: int, m: int) -> int:
        """完美洗牌（循环左移一位）"""
        M = 1 << m
        return ((j << 1) & (M - 1)) | ((j >> (m - 1)) & 1)

    @staticmethod
    def inverse_perfect_shuffle(j: int, m: int) -> int:
        """逆完美洗牌（循环右移一位）"""
        M = 1 << m
        return (j >> 1) | ((j & 1) << (m - 1))

    @classmethod
    def build(cls, N: int) -> NetworkTopology:
        """构建 Benes 网络拓扑 - 使用简化的直连模式演示"""
        if not (N > 0 and (N & (N - 1)) == 0):
            raise ValueError("N 必须是 2 的幂")

        k = int(math.log2(N))
        num_stages = 2 * k - 1
        switches_per_stage = N // 2

        topology = NetworkTopology()

        # 创建输入端口
        for i in range(N):
            topology.input_ports.append(Port(i, is_input=True))

        # 创建输出端口
        for i in range(N):
            topology.output_ports.append(Port(i, is_input=False))

        # 创建各级开关
        for s in range(num_stages):
            stage = []
            for i in range(switches_per_stage):
                stage.append(SwitchNode(s, i))
            topology.add_stage(stage)

        # 连接输入到第一级
        for i in range(switches_per_stage):
            topology.add_connection(topology.input_ports[2*i].endpoint, topology.stages[0][i].inputs[0])
            topology.add_connection(topology.input_ports[2*i+1].endpoint, topology.stages[0][i].inputs[1])

        # 连接级间（直连模式，作为基础演示）
        # 同时也加入一些洗牌连接来演示
        for s in range(num_stages - 1):
            curr_stage = topology.stages[s]
            next_stage = topology.stages[s + 1]

            M = N
            if s < k - 1:
                # 前半部分用洗牌连接
                m = k - s
                M = 1 << m
                num_blocks = N // M

                for block in range(num_blocks):
                    block_start = block * (M // 2)
                    src_eps = []
                    for i in range(M // 2):
                        src_eps.append(curr_stage[block_start + i].outputs[0])
                        src_eps.append(curr_stage[block_start + i].outputs[1])

                    for j in range(M):
                        shuffled_j = cls.perfect_shuffle(j, int(math.log2(M)))
                        dst_sw = block_start + (shuffled_j // 2)
                        dst_port = shuffled_j % 2
                        topology.add_connection(src_eps[j], next_stage[dst_sw].inputs[dst_port])
            else:
                # 后半部分用逆洗牌或直连
                for i in range(switches_per_stage):
                    topology.add_connection(curr_stage[i].outputs[0], next_stage[i].inputs[0])
                    topology.add_connection(curr_stage[i].outputs[1], next_stage[i].inputs[1])

        # 连接最后一级到输出
        for i in range(switches_per_stage):
            topology.add_connection(topology.stages[-1][i].outputs[0], topology.output_ports[2*i].endpoint)
            topology.add_connection(topology.stages[-1][i].outputs[1], topology.output_ports[2*i+1].endpoint)

        return topology


# =============================================================================
# 通用网络拓扑生成器
# =============================================================================

class GenericTopologyBuilder:
    """通用多级网络拓扑生成器"""

    @staticmethod
    def build_straight_through(
        num_stages: int,
        switches_per_stage: int,
        num_inputs: Optional[int] = None
    ) -> NetworkTopology:
        """
        构建直连模式的通用网络

        Args:
            num_stages: 级数
            switches_per_stage: 每级开关数量
            num_inputs: 输入端口数量（默认为 2*switches_per_stage）

        Returns:
            构建好的 NetworkTopology
        """
        if num_inputs is None:
            num_inputs = 2 * switches_per_stage

        num_outputs = num_inputs

        topology = NetworkTopology()

        # 创建输入端口
        for i in range(num_inputs):
            topology.input_ports.append(Port(i, is_input=True))

        # 创建输出端口
        for i in range(num_outputs):
            topology.output_ports.append(Port(i, is_input=False))

        # 创建各级开关
        for s in range(num_stages):
            stage = []
            for i in range(switches_per_stage):
                stage.append(SwitchNode(s, i))
            topology.add_stage(stage)

        # 连接输入到第一级
        for i in range(min(switches_per_stage * 2, num_inputs)):
            switch_idx = i // 2
            port_idx = i % 2
            if switch_idx < len(topology.stages[0]):
                topology.add_connection(
                    topology.input_ports[i].endpoint,
                    topology.stages[0][switch_idx].inputs[port_idx]
                )

        # 连接级间（直连模式）
        for s in range(num_stages - 1):
            curr_stage = topology.stages[s]
            next_stage = topology.stages[s + 1]
            for i in range(min(len(curr_stage), len(next_stage))):
                topology.add_connection(curr_stage[i].outputs[0], next_stage[i].inputs[0])
                topology.add_connection(curr_stage[i].outputs[1], next_stage[i].inputs[1])

        # 连接最后一级到输出
        last_stage = topology.stages[-1]
        for i in range(min(switches_per_stage * 2, num_outputs)):
            switch_idx = i // 2
            port_idx = i % 2
            if switch_idx < len(last_stage):
                topology.add_connection(
                    last_stage[switch_idx].outputs[port_idx],
                    topology.output_ports[i].endpoint
                )

        return topology


# =============================================================================
# 图形项 - 美观的端口节点
# =============================================================================

class PortGraphicsItem(QGraphicsEllipseItem):
    """输入/输出端口图形项 - 美观的圆形节点"""

    def __init__(self, port: Port, parent=None):
        super().__init__(parent)
        self.port = port
        self.setAcceptHoverEvents(True)
        self.setFlag(QGraphicsItem.ItemIsSelectable, False)
        self._update_appearance()

    def _update_appearance(self):
        """更新外观"""
        # 使用渐变色
        if self.port.is_input:
            base_color = QColor(70, 130, 180)  # 钢蓝色
        else:
            base_color = QColor(60, 179, 113)   # 海绿色

        self.setBrush(QBrush(base_color))
        self.setPen(QPen(QColor(40, 40, 40), 2))

    def update_position(self):
        """更新位置"""
        r = self.port.radius
        self.setRect(QRectF(
            self.port.x - r,
            self.port.y - r,
            r * 2, r * 2
        ))


# =============================================================================
# 图形项 - 美观的开关
# =============================================================================

class SwitchGraphicsItem(QGraphicsItem):
    """美观的开关图形项 - 自定义绘制"""

    COLOR_THROUGH_BG = QColor(100, 200, 100)   # 绿色背景 = 直通
    COLOR_CROSS_BG = QColor(255, 180, 80)       # 橙色背景 = 交叉
    COLOR_BORDER = QColor(50, 50, 50)
    COLOR_ARROW_THROUGH = QColor(30, 100, 30)
    COLOR_ARROW_CROSS = QColor(150, 80, 20)

    def __init__(self, switch: SwitchNode, parent=None):
        super().__init__(parent)
        self.switch = switch
        self.setAcceptHoverEvents(True)
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setCursor(Qt.PointingHandCursor)

    def boundingRect(self) -> QRectF:
        """返回边界矩形"""
        w = self.switch.width
        h = self.switch.height
        return QRectF(-w/2 - 5, -h/2 - 5, w + 10, h + 10)

    def paint(self, painter: QPainter, option, widget=None):
        """绘制美观的开关"""
        painter.setRenderHint(QPainter.Antialiasing)
        w = self.switch.width
        h = self.switch.height

        # 绘制背景圆角矩形
        rect = QRectF(-w/2, -h/2, w, h)

        # 根据状态选择颜色
        if self.switch.state == 0:
            bg_color = self.COLOR_THROUGH_BG
            arrow_color = self.COLOR_ARROW_THROUGH
        else:
            bg_color = self.COLOR_CROSS_BG
            arrow_color = self.COLOR_ARROW_CROSS

        # 绘制渐变背景
        gradient = QLinearGradient(0, -h/2, 0, h/2)
        gradient.setColorAt(0, bg_color.lighter(120))
        gradient.setColorAt(0.5, bg_color)
        gradient.setColorAt(1, bg_color.darker(120))

        painter.setBrush(QBrush(gradient))
        painter.setPen(QPen(self.COLOR_BORDER, 2))
        painter.drawRoundedRect(rect, 8, 8)

        # 绘制内部状态指示线
        painter.setPen(QPen(arrow_color, 2.5))
        half_h = h * 0.3

        if self.switch.state == 0:
            # 直通状态：两条平行线
            painter.drawLine(QPointF(-w/2 + 8, -half_h), QPointF(w/2 - 8, -half_h))
            painter.drawLine(QPointF(-w/2 + 8, half_h), QPointF(w/2 - 8, half_h))

            # 箭头
            self._draw_arrow(painter, QPointF(w/2 - 12, -half_h), arrow_color, 0)
            self._draw_arrow(painter, QPointF(w/2 - 12, half_h), arrow_color, 0)
        else:
            # 交叉状态：两条交叉线
            painter.drawLine(QPointF(-w/2 + 8, -half_h), QPointF(w/2 - 8, half_h))
            painter.drawLine(QPointF(-w/2 + 8, half_h), QPointF(w/2 - 8, -half_h))

            # 箭头
            self._draw_arrow(painter, QPointF(w/2 - 12, half_h), arrow_color, 0)
            self._draw_arrow(painter, QPointF(w/2 - 12, -half_h), arrow_color, 0)

        # 绘制输入/输出端口小圆点
        painter.setBrush(QBrush(QColor(60, 60, 60)))
        painter.setPen(QPen(QColor(30, 30, 30), 1))
        dot_r = 4

        # 输入端点
        painter.drawEllipse(QPointF(-w/2, -half_h), dot_r, dot_r)
        painter.drawEllipse(QPointF(-w/2, half_h), dot_r, dot_r)

        # 输出端点
        painter.drawEllipse(QPointF(w/2, -half_h), dot_r, dot_r)
        painter.drawEllipse(QPointF(w/2, half_h), dot_r, dot_r)

    def _draw_arrow(self, painter: QPainter, pos: QPointF, color: QColor, direction: int):
        """绘制小箭头"""
        painter.setBrush(QBrush(color))
        painter.setPen(QPen(color, 1))

        arrow_size = 6
        path = QPainterPath()
        path.moveTo(pos.x() + arrow_size, pos.y())
        path.lineTo(pos.x(), pos.y() - arrow_size/2)
        path.lineTo(pos.x(), pos.y() + arrow_size/2)
        path.closeSubpath()
        painter.drawPath(path)

    def update_position(self):
        """更新位置"""
        self.setPos(self.switch.x, self.switch.y)

    def toggle(self):
        """切换开关状态"""
        self.switch.toggle()
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.toggle()
            # 通知父视图更新数据流
            scene = self.scene()
            if scene:
                for view in scene.views():
                    if hasattr(view, 'update_data_flow') and hasattr(view, '_update_stats'):
                        view.update_data_flow()
                        view._update_stats()
        super().mousePressEvent(event)


class ConnectionGraphicsItem(QGraphicsLineItem):
    """连接线图形项"""

    def __init__(self, connection: Connection, parent=None):
        super().__init__(parent)
        self.connection = connection
        self.setPen(QPen(QColor(100, 100, 100), 2.5))

    def update_position(self):
        """更新位置"""
        self.setLine(QLineF(
            self.connection.src.x,
            self.connection.src.y,
            self.connection.dst.x,
            self.connection.dst.y
        ))

    def update_color(self, num_inputs: int):
        """根据数据源更新颜色"""
        if self.connection.data_source >= 0:
            color = ColorManager.get_color(self.connection.data_source, num_inputs)
        else:
            color = QColor(210, 210, 210)  # 浅灰色表示未使用
        self.setPen(QPen(color, 2.5))


class PortLabelItem(QGraphicsTextItem):
    """端口标签图形项"""

    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        font = QFont()
        font.setPointSize(11)
        font.setBold(True)
        self.setFont(font)
        self.setDefaultTextColor(Qt.black)


# =============================================================================
# 网络视图
# =============================================================================

class NetworkGraphicsView(QGraphicsView):
    """网络图形视图 - 支持滚动"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        self.setRenderHint(QPainter.Antialiasing)
        self.setBackgroundBrush(QBrush(QColor(245, 245, 250)))

        # 启用滚动条
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setDragMode(QGraphicsView.NoDrag)

        self.topology: Optional[NetworkTopology] = None
        self.switch_items: List[SwitchGraphicsItem] = []
        self.port_items: List[PortGraphicsItem] = []
        self.connection_items: List[ConnectionGraphicsItem] = []
        self.input_label_items: List[PortLabelItem] = []
        self.output_label_items: List[PortLabelItem] = []
        self._stats_callback: Optional[Callable] = None

        self.layout = LayoutCalculator()

    def set_stats_callback(self, callback: Callable):
        """设置统计信息更新回调"""
        self._stats_callback = callback

    def _update_stats(self):
        """更新统计信息（通过回调）"""
        if self._stats_callback:
            self._stats_callback()

    def set_topology(self, topology: NetworkTopology):
        """设置拓扑并重建图形项"""
        self.topology = topology
        self._rebuild_scene()

    def _rebuild_scene(self):
        """重建场景中的所有图形项"""
        self.scene.clear()
        self.switch_items = []
        self.port_items = []
        self.connection_items = []
        self.input_label_items = []
        self.output_label_items = []

        if not self.topology:
            return

        # 创建连接线（在底层）
        for conn in self.topology.connections:
            item = ConnectionGraphicsItem(conn)
            self.connection_items.append(item)
            self.scene.addItem(item)

        # 创建输入端口
        for port in self.topology.input_ports:
            item = PortGraphicsItem(port)
            self.port_items.append(item)
            self.scene.addItem(item)

        # 创建输出端口
        for port in self.topology.output_ports:
            item = PortGraphicsItem(port)
            self.port_items.append(item)
            self.scene.addItem(item)

        # 创建开关（在上层）
        for stage in self.topology.stages:
            for switch in stage:
                item = SwitchGraphicsItem(switch)
                self.switch_items.append(item)
                self.scene.addItem(item)

        # 创建输入标签
        for port in self.topology.input_ports:
            label = PortLabelItem(f"In {port.port_idx}")
            self.input_label_items.append(label)
            self.scene.addItem(label)

        # 创建输出标签
        for port in self.topology.output_ports:
            label = PortLabelItem("Out ?")
            self.output_label_items.append(label)
            self.scene.addItem(label)

        # 更新布局和数据流
        self.update_layout()

    def update_layout(self):
        """更新布局 - 水平不滚动，垂直可滚动"""
        if not self.topology:
            return

        # 计算需要的尺寸
        num_inputs = len(self.topology.input_ports)
        num_outputs = len(self.topology.output_ports)
        num_stages = len(self.topology.stages)

        # 水平方向：使用视图宽度，不滚动
        viewport_rect = self.viewport().rect()
        width = max(viewport_rect.width(), 400)

        # 垂直方向：根据元素数量计算高度，支持滚动
        min_height = 200 + max(num_inputs, num_outputs) * 55
        height = max(viewport_rect.height(), min_height)

        # 计算布局
        self.layout.calculate(self.topology, width, height)

        # 更新场景大小：宽度用视图宽，高度用计算的高度
        self.scene.setSceneRect(0, 0, width, height)

        # 更新所有图形项位置
        for item in self.connection_items:
            item.update_position()

        for item in self.port_items:
            item.update_position()

        for item in self.switch_items:
            item.update_position()

        for i, port in enumerate(self.topology.input_ports):
            label = self.input_label_items[i]
            # 输入标签放在输入节点右边，往上一点避免重叠
            label.setPos(port.x + port.radius + 8, port.y - 18)
            label.setPlainText(f"{i}")
            label.setDefaultTextColor(QColor(0, 0, 0))  # 黑色

        for i, port in enumerate(self.topology.output_ports):
            label = self.output_label_items[i]
            # 输出标签放在输出节点左边，往上一点避免重叠
            label.setPos(port.x - port.radius - 35, port.y - 18)

        # 更新数据流和颜色
        self.update_data_flow()

    def update_data_flow(self):
        """更新数据流显示"""
        if not self.topology:
            return

        # 传播数据流
        DataFlowPropagator.propagate(self.topology)

        # 更新连线颜色
        num_inputs = len(self.topology.input_ports)
        for item in self.connection_items:
            item.update_color(num_inputs)

        # 更新输出标签
        # 建立端点到输入源的映射
        ep_to_source: Dict[Endpoint, int] = {}
        for port in self.topology.input_ports:
            ep_to_source[port.endpoint] = port.port_idx

        # 传播这个映射
        changed = True
        while changed:
            changed = False
            for conn in self.topology.connections:
                if conn.src in ep_to_source and conn.dst not in ep_to_source:
                    ep_to_source[conn.dst] = ep_to_source[conn.src]
                    changed = True

        # 更新输出标签 - 始终显示追踪到的来源
        for i, port in enumerate(self.topology.output_ports):
            source = ep_to_source.get(port.endpoint, -1)
            # 如果没有找到，尝试通过连接反向查找
            if source < 0:
                for conn in self.topology.connections:
                    if conn.dst == port.endpoint:
                        source = conn.data_source
                        break
            # 如果还是找不到，显示 0 作为默认
            if source < 0:
                source = 0
            self.output_label_items[i].setPlainText(f"{source}")
            self.output_label_items[i].setDefaultTextColor(QColor(0, 0, 0))  # 黑色

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_layout()


# =============================================================================
# 主窗口
# =============================================================================

class MainWindow(QMainWindow):
    """主窗口"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("多级互连网络可视化 - Benes 网络")
        self.setMinimumSize(1200, 800)
        self.resize(1400, 900)

        # 创建中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # 主布局
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 创建网络视图
        self.network_view = NetworkGraphicsView()
        self.network_view.set_stats_callback(self._update_stats)
        main_layout.addWidget(self.network_view, stretch=4)

        # 创建控制面板
        control_panel = self._create_control_panel()
        main_layout.addWidget(control_panel, stretch=1)

        # 初始化 Benes 网络
        self._switch_to_benes_mode()

    def _create_control_panel(self) -> QWidget:
        """创建控制面板"""
        panel = QWidget()
        panel.setMaximumWidth(300)
        layout = QVBoxLayout(panel)
        layout.setSpacing(12)
        layout.setContentsMargins(15, 15, 15, 15)

        # 网络类型选择
        type_group = QGroupBox("网络类型")
        type_layout = QVBoxLayout()
        self.network_type_combo = QComboBox()
        self.network_type_combo.addItem("Benes 网络", "benes")
        self.network_type_combo.addItem("通用模式", "generic")
        self.network_type_combo.currentIndexChanged.connect(self._on_network_type_changed)
        type_layout.addWidget(self.network_type_combo)
        type_group.setLayout(type_layout)
        layout.addWidget(type_group)

        # Benes 网络配置
        self.benes_group = QGroupBox("Benes 网络配置")
        benes_layout = QFormLayout()
        self.benes_size_combo = QComboBox()
        for n in [2, 4, 8, 16, 32, 64]:
            self.benes_size_combo.addItem(f"N = {n}", n)
        self.benes_size_combo.setCurrentIndex(2)  # 默认 N=8
        self.benes_size_combo.currentIndexChanged.connect(self._on_benes_size_changed)
        benes_layout.addRow("网络规模:", self.benes_size_combo)
        self.benes_group.setLayout(benes_layout)
        layout.addWidget(self.benes_group)

        # 通用模式配置
        self.generic_group = QGroupBox("通用模式配置")
        generic_layout = QFormLayout()
        self.num_stages_spin = QSpinBox()
        self.num_stages_spin.setRange(1, 10)
        self.num_stages_spin.setValue(3)
        self.num_stages_spin.valueChanged.connect(self._on_generic_config_changed)
        generic_layout.addRow("级数:", self.num_stages_spin)

        self.switches_per_stage_spin = QSpinBox()
        self.switches_per_stage_spin.setRange(1, 32)
        self.switches_per_stage_spin.setValue(4)
        self.switches_per_stage_spin.valueChanged.connect(self._on_generic_config_changed)
        generic_layout.addRow("每级开关数:", self.switches_per_stage_spin)
        self.generic_group.setLayout(generic_layout)
        layout.addWidget(self.generic_group)

        # 控制位操作
        control_bits_group = QGroupBox("控制位操作")
        control_bits_layout = QVBoxLayout()
        self.control_bits_text = QTextEdit()
        self.control_bits_text.setMaximumHeight(80)
        self.control_bits_text.setPlaceholderText("输入二进制字符串 (例如: 010101)")
        control_bits_layout.addWidget(self.control_bits_text)

        bits_button_layout = QHBoxLayout()
        self.load_bits_btn = QPushButton("加载")
        self.load_bits_btn.clicked.connect(self._load_control_bits)
        bits_button_layout.addWidget(self.load_bits_btn)

        self.export_bits_btn = QPushButton("导出")
        self.export_bits_btn.clicked.connect(self._export_control_bits)
        bits_button_layout.addWidget(self.export_bits_btn)
        control_bits_layout.addLayout(bits_button_layout)
        control_bits_group.setLayout(control_bits_layout)
        layout.addWidget(control_bits_group)

        # 快捷操作
        action_group = QGroupBox("快捷操作")
        action_layout = QVBoxLayout()
        self.random_btn = QPushButton("随机状态")
        self.random_btn.clicked.connect(self._randomize_states)
        action_layout.addWidget(self.random_btn)

        self.reset_btn = QPushButton("重置为直通")
        self.reset_btn.clicked.connect(self._reset_to_through)
        action_layout.addWidget(self.reset_btn)
        action_group.setLayout(action_layout)
        layout.addWidget(action_group)

        # 统计信息
        stats_group = QGroupBox("统计信息")
        stats_layout = QFormLayout()
        self.total_switches_label = QLabel("0")
        stats_layout.addRow("总开关数:", self.total_switches_label)

        self.cross_switches_label = QLabel("0")
        stats_layout.addRow("交叉开关数:", self.cross_switches_label)
        stats_group.setLayout(stats_layout)
        layout.addWidget(stats_group)

        layout.addStretch()

        return panel

    def _on_network_type_changed(self):
        """网络类型改变"""
        self._update_ui_visibility()
        if self.network_type_combo.currentData() == "benes":
            self._switch_to_benes_mode()
        else:
            self._switch_to_generic_mode()

    def _update_ui_visibility(self):
        """更新 UI 可见性"""
        is_benes = self.network_type_combo.currentData() == "benes"
        self.benes_group.setEnabled(is_benes)
        self.generic_group.setEnabled(not is_benes)

    def _on_benes_size_changed(self):
        """Benes 网络规模改变"""
        self._switch_to_benes_mode()

    def _on_generic_config_changed(self):
        """通用配置改变"""
        self._switch_to_generic_mode()

    def _switch_to_benes_mode(self):
        """切换到 Benes 模式"""
        n = self.benes_size_combo.currentData()
        if n is None:
            n = 8
        topology = BenesTopologyBuilder.build(n)
        self.network_view.set_topology(topology)
        self._update_stats()

    def _switch_to_generic_mode(self):
        """切换到通用模式"""
        num_stages = self.num_stages_spin.value()
        switches_per_stage = self.switches_per_stage_spin.value()
        topology = GenericTopologyBuilder.build_straight_through(
            num_stages, switches_per_stage
        )
        self.network_view.set_topology(topology)
        self._update_stats()

    def _load_control_bits(self):
        """加载控制位"""
        text = self.control_bits_text.toPlainText().strip()
        # 只保留 0 和 1
        bits = [c for c in text if c in ('0', '1')]

        if not self.network_view.topology:
            return

        switches = self.network_view.topology.all_switches()

        if len(bits) != len(switches):
            self.control_bits_text.setPlainText(f"错误: 需要 {len(switches)} 位，实际 {len(bits)} 位")
            return

        for i, sw in enumerate(switches):
            sw.state = int(bits[i])

        # 更新图形项
        for item in self.network_view.switch_items:
            item.update()

        self.network_view.update_data_flow()
        self._update_stats()

    def _export_control_bits(self):
        """导出控制位"""
        if not self.network_view.topology:
            return

        switches = self.network_view.topology.all_switches()
        bits = ''.join(str(sw.state) for sw in switches)
        self.control_bits_text.setPlainText(bits)

    def _randomize_states(self):
        """随机化开关状态"""
        if not self.network_view.topology:
            return

        for sw in self.network_view.topology.all_switches():
            sw.state = random.randint(0, 1)

        for item in self.network_view.switch_items:
            item.update()

        self.network_view.update_data_flow()
        self._update_stats()

    def _reset_to_through(self):
        """重置为直通状态"""
        if not self.network_view.topology:
            return

        for sw in self.network_view.topology.all_switches():
            sw.state = 0

        for item in self.network_view.switch_items:
            item.update()

        self.network_view.update_data_flow()
        self._update_stats()

    def _update_stats(self):
        """更新统计信息"""
        if not self.network_view.topology:
            self.total_switches_label.setText("0")
            self.cross_switches_label.setText("0")
            return

        switches = self.network_view.topology.all_switches()
        total = len(switches)
        cross = sum(1 for sw in switches if sw.state == 1)

        self.total_switches_label.setText(str(total))
        self.cross_switches_label.setText(str(cross))


# =============================================================================
# 程序入口
# =============================================================================

def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
