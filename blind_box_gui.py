#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
B站直播间盲盒盈亏统计工具 - GUI版本
适用于直播时的实时监控
"""

import sys
import json
import struct
import zlib
import brotli
import time
import requests
import asyncio
import aiohttp
import hashlib
import urllib.parse
import re
import os
from pathlib import Path
from datetime import datetime, date
from typing import Dict, List, Optional, Tuple
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QLineEdit, QTextEdit, QTableWidget,
    QTableWidgetItem, QGroupBox, QHeaderView, QSplitter,
    QMessageBox, QFrame
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QColor, QFont, QBrush

# ==================== 配置 ====================
MIXIN_KEY_ENC_TAB = [
    46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35, 27, 43, 5, 49,
    33, 9, 42, 19, 29, 28, 14, 39, 12, 38, 41, 13, 37, 48, 7, 16, 24, 55, 40,
    61, 26, 17, 0, 1, 60, 51, 30, 4, 22, 25, 54, 21, 56, 59, 6, 63, 57, 62, 11,
    36, 20, 34, 44, 52
]

# 默认配置
DEFAULT_ROOM_ID = "24872476"
DEFAULT_COOKIE = ""  # 用户需要填入自己的Cookie
WEB_SERVER_URL = "http://localhost:5000"
DATA_DIR = Path("data")  # 数据保存目录
DATA_FILE = DATA_DIR / f"blind_box_data_{date.today().isoformat()}.json"  # 当日数据文件
# ==============================================


def generate_wbi_sign(params: dict, img_key: str, sub_key: str) -> dict:
    """生成WBI签名"""
    raw_wbi_key = img_key + sub_key
    mixin_key = ''.join(raw_wbi_key[i] for i in MIXIN_KEY_ENC_TAB)[:32]

    params = params.copy()
    params['wts'] = params.get('wts', int(time.time()))

    sorted_params = sorted(params.items())
    filtered_params = {
        k: ''.join(c for c in str(v) if c not in "!'()*")
        for k, v in sorted_params
    }

    query_parts = []
    for k, v in filtered_params.items():
        encoded_key = urllib.parse.quote(str(k), safe='')
        encoded_value = urllib.parse.quote(str(v), safe='').replace('+', '%20')
        query_parts.append(f"{encoded_key}={encoded_value}")
    query_string = '&'.join(query_parts)

    w_rid = hashlib.md5((query_string + mixin_key).encode()).hexdigest()

    result = params.copy()
    result['w_rid'] = w_rid
    return result


def encode_packet(data: bytes, op_code: int) -> bytes:
    """编码数据包"""
    body_len = len(data)
    header = struct.pack('>IHHII',
                        16 + body_len,
                        16,
                        1,
                        op_code,
                        1)
    return header + data


def decode_packet(data: bytes):
    """解码数据包"""
    if len(data) < 16:
        return 0, 0, b''
    total_len, header_len, ver, op_code, seq = struct.unpack('>IHHII', data[:16])
    body = data[header_len:total_len]
    return ver, op_code, body


def decompress_body(body: bytes, ver: int) -> bytes:
    """解压数据"""
    if ver == 2:
        return zlib.decompress(body)
    elif ver == 3:
        return brotli.decompress(body)
    else:
        return body


def extract_uid_from_cookie(cookie: str) -> int:
    """从Cookie中提取DedeUserID"""
    match = re.search(r'DedeUserID=(\d+)', cookie)
    if match:
        return int(match.group(1))
    return 0


async def get_real_room_id(room_id: int, headers: dict) -> Tuple[Optional[int], Optional[str]]:
    """获取真实房间号和房间标题"""
    url = "https://api.live.bilibili.com/xlive/web-room/v1/index/getInfoByRoom"
    params = {"room_id": room_id}

    uncompressed_headers = headers.copy()
    uncompressed_headers['Accept-Encoding'] = 'gzip'

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, headers=uncompressed_headers, compress=False) as resp:
                data = await resp.json()
                if resp.status == 200 and data['code'] == 0:
                    room_info = data['data']['room_info']
                    return room_info['room_id'], room_info.get('title', '未知标题')
    except Exception:
        pass
    return None, None


async def get_wbi_keys(headers: dict) -> Tuple[str, str]:
    """获取WBI签名所需的key"""
    url = "https://api.bilibili.com/x/web-interface/nav"

    uncompressed_headers = headers.copy()
    uncompressed_headers['Accept-Encoding'] = 'gzip'

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=uncompressed_headers, compress=False) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data['code'] == 0:
                        wbi_img = data['data']['wbi_img']['img_url']
                        wbi_sub = data['data']['wbi_img']['sub_url']
                        img_key = wbi_img.split('/')[-1].split('.')[0]
                        sub_key = wbi_sub.split('/')[-1].split('.')[0]
                        return img_key, sub_key
    except Exception:
        pass
    return "", ""


async def get_danmu_info(room_id: int, headers: dict) -> Tuple[Optional[Dict], Optional[int], Optional[str]]:
    """获取弹幕连接信息、真实房间号和房间标题"""
    real_room_id, room_title = await get_real_room_id(room_id, headers)
    if not real_room_id:
        return None, None, None

    wbi_keys = await get_wbi_keys(headers)
    if not wbi_keys:
        return None, None, None

    img_key, sub_key = wbi_keys
    wts = int(time.time())

    base_url = "https://api.live.bilibili.com/xlive/web-room/v1/index/getDanmuInfo"
    params = {
        "id": real_room_id,
        "type": 0,
        "wts": wts
    }

    signed_params = generate_wbi_sign(params, img_key, sub_key)

    query_parts = []
    for k, v in sorted(signed_params.items()):
        encoded_key = urllib.parse.quote(str(k), safe='')
        encoded_value = urllib.parse.quote(str(v), safe='')
        query_parts.append(f"{encoded_key}={encoded_value}")
    query_string = '&'.join(query_parts)
    full_url = f"{base_url}?{query_string}"

    uncompressed_headers = headers.copy()
    uncompressed_headers['Accept-Encoding'] = 'gzip'

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(full_url, headers=uncompressed_headers, compress=False) as resp:
                data = await resp.json()
                if resp.status == 200 and data['code'] == 0:
                    return data['data'], real_room_id, room_title
    except Exception:
        pass
    return None, None, None


# ==================== 监听线程 ====================

class BlindBoxListenerThread(QThread):
    """盲盒监听线程"""

    # 信号定义
    on_connected = pyqtSignal(str)  # 连接成功，参数：房间标题
    on_error = pyqtSignal(str)  # 错误信息
    on_blind_box = pyqtSignal(dict)  # 新盲盒数据
    on_status_update = pyqtSignal(str)  # 状态更新
    on_disconnected = pyqtSignal()  # 断开连接

    def __init__(self, room_id: int, cookie: str):
        super().__init__()
        self.room_id = room_id
        self.cookie = cookie
        self.running = False
        self.loop = None
        self.stop_event = None  # 停止事件

    def run(self):
        """运行监听"""
        self.running = True
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.stop_event = asyncio.Event()

        try:
            self.loop.run_until_complete(self._listen())
        except RuntimeError as e:
            if "Event loop stopped" not in str(e):
                raise  # 只忽略停止相关的错误
        finally:
            self.loop.close()

    async def _listen(self):
        """监听主逻辑"""
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'https://live.bilibili.com/',
            'Cookie': self.cookie,
            'Accept-Encoding': 'gzip'
        }

        user_id = extract_uid_from_cookie(self.cookie)

        self.on_status_update.emit(f"正在连接直播间 {self.room_id}...")

        danmu_info, real_room_id, room_title = await get_danmu_info(self.room_id, headers)
        if not danmu_info or not real_room_id:
            self.on_error.emit("获取房间信息失败，请检查Cookie和房间号")
            return

        host_info = danmu_info['host_list'][0]
        ws_url = f"wss://{host_info['host']}:{host_info['wss_port']}/sub"
        token = danmu_info['token']

        try:
            async with aiohttp.ClientSession() as session:
                async with session.ws_connect(ws_url) as ws:
                    await asyncio.sleep(0.5)
                    if ws.closed:
                        self.on_error.emit("WebSocket连接已关闭")
                        return

                    auth_data = json.dumps({
                        "uid": user_id,
                        "roomid": real_room_id,
                        "protover": 3,
                        "platform": "web",
                        "type": 2,
                        "key": token
                    }, ensure_ascii=False).encode('utf-8')

                    await ws.send_bytes(encode_packet(auth_data, 7))

                    # 等待认证响应
                    for _ in range(10):
                        if self.stop_event.is_set():
                            return
                        try:
                            msg = await asyncio.wait_for(ws.receive(), timeout=0.5)
                            if msg.type == aiohttp.WSMsgType.BINARY:
                                ver, op_code, body = decode_packet(msg.data)
                                body_data = decompress_body(body, ver)
                                if body_data:
                                    break
                        except asyncio.TimeoutError:
                            continue

                    await asyncio.sleep(1)
                    if ws.closed or self.stop_event.is_set():
                        if self.stop_event.is_set():
                            return
                        self.on_error.emit("认证失败")
                        return

                    self.on_connected.emit(room_title)
                    self.on_status_update.emit("正在监听盲盒...")

                    # 启动心跳和消息监听
                    heartbeat_task = asyncio.create_task(self._heartbeat(ws))
                    message_task = asyncio.create_task(self._message_listener(ws))
                    stop_task = asyncio.create_task(self.stop_event.wait())

                    done, pending = await asyncio.wait(
                        [heartbeat_task, message_task, stop_task],
                        return_when=asyncio.FIRST_COMPLETED
                    )

                    for task in pending:
                        task.cancel()

        except Exception as e:
            if self.stop_event.is_set():
                return  # 停止时忽略错误
            self.on_error.emit(f"连接错误: {str(e)}")
        finally:
            self.on_disconnected.emit()

    async def _heartbeat(self, ws):
        """心跳任务"""
        try:
            while not ws.closed and self.running:
                try:
                    await asyncio.wait_for(self.stop_event.wait(), timeout=30)
                    return  # 停止事件被设置
                except asyncio.TimeoutError:
                    pass  # 超时继续心跳

                if ws.closed or not self.running:
                    break
                await ws.send_bytes(encode_packet(b'', 2))
        except asyncio.CancelledError:
            pass
        except Exception:
            pass

    async def _message_listener(self, ws):
        """消息监听任务"""
        try:
            while not ws.closed and self.running:
                try:
                    # 同时等待消息和停止事件
                    receive_task = asyncio.create_task(ws.receive())
                    stop_task = asyncio.create_task(self.stop_event.wait())

                    done, pending = await asyncio.wait(
                        [receive_task, stop_task],
                        return_when=asyncio.FIRST_COMPLETED
                    )

                    # 取消未完成的任务
                    for task in pending:
                        task.cancel()

                    # 检查是否是停止事件触发
                    if stop_task in done:
                        return  # 停止事件被设置，退出

                    # 获取消息（receive_task 已经完成）
                    msg = receive_task.result()

                    if msg.type == aiohttp.WSMsgType.BINARY:
                        try:
                            ver, op_code, body = decode_packet(msg.data)
                            body_data = decompress_body(body, ver)

                            if body_data:
                                try:
                                    json_text = body_data.decode('utf-8', errors='ignore')

                                    # 括号匹配找到每个JSON对象
                                    pos = 0
                                    while pos < len(json_text):
                                        if json_text[pos] != '{':
                                            pos += 1
                                            continue

                                        bracket_count = 0
                                        start = pos
                                        end = -1

                                        for i in range(pos, len(json_text)):
                                            if json_text[i] == '{':
                                                bracket_count += 1
                                            elif json_text[i] == '}':
                                                bracket_count -= 1
                                                if bracket_count == 0:
                                                    end = i + 1
                                                    break

                                        if end == -1:
                                            break

                                        full_json = json_text[start:end]

                                        try:
                                            json_data = json.loads(full_json)
                                            cmd = json_data.get('cmd', '')

                                            # 只处理盲盒礼物
                                            if cmd == 'SEND_GIFT':
                                                data = json_data.get('data', {})
                                                blind_gift = data.get('blind_gift')

                                                if blind_gift:
                                                    uid = data.get('uid', 0)
                                                    uname = data.get('uname', '未知')
                                                    blind_box_name = blind_gift.get('original_gift_name', '未知')  # 盲盒名称

                                                    # 计算价格
                                                    blind_price = blind_gift.get('original_gift_price', 0)
                                                    gift_price = blind_gift.get('gift_tip_price', 0)

                                                    # B站API不返回爆出礼物名称，显示价格
                                                    gift_price_yuan = gift_price / 1000
                                                    gift_display = f"{gift_price_yuan:.1f}元礼物"

                                                    profit = (gift_price - blind_price) / 1000
                                                    blind_price_yuan = blind_price / 1000

                                                    # 发送信号
                                                    self.on_blind_box.emit({
                                                        'uid': uid,
                                                        'uname': uname,
                                                        'blind_name': blind_box_name,  # 盲盒类型
                                                        'gift_name': gift_display,  # 爆出礼物（显示价格）
                                                        'cost': blind_price_yuan,
                                                        'value': gift_price_yuan,
                                                        'profit': profit,
                                                        'time': datetime.now().strftime("%H:%M:%S")
                                                    })

                                                    # 发送到Web服务器
                                                    self._send_to_web_server(uid, uname, blind_box_name,
                                                                            blind_price, gift_price, gift_display)

                                        except json.JSONDecodeError:
                                            pass

                                        pos = end

                                except Exception:
                                    pass

                        except Exception:
                            pass

                    elif msg.type == aiohttp.WSMsgType.CLOSED:
                        break

                except asyncio.TimeoutError:
                    pass

        except asyncio.CancelledError:
            pass
        except Exception:
            pass

    def _send_to_web_server(self, uid: int, uname: str, blind_box_name: str,
                           blind_price: int, gift_price: int, gift_name: str):
        """发送盲盒数据到Web服务器"""
        try:
            requests.post(
                f"{WEB_SERVER_URL}/api/blind_box",
                json={
                    'uid': uid,
                    'uname': uname,
                    'blind_name': blind_box_name,
                    'blind_price': blind_price,
                    'gift_price': gift_price,
                    'gift_name': gift_name  # 爆出礼物名称（为未来扩展预留）
                },
                timeout=1
            )
        except:
            pass  # 静默失败

    def stop(self):
        """停止监听"""
        self.running = False
        if self.stop_event:
            self.loop.call_soon_threadsafe(self.stop_event.set)


# ==================== 主窗口 ====================

class BlindBoxStatsWindow(QMainWindow):
    """盲盒统计主窗口"""

    def __init__(self):
        super().__init__()
        self.listener_thread = None
        self.blind_box_count = 0
        self.profit_count = 0  # 盈利盲盒数量
        self.loss_count = 0  # 亏损盲盒数量
        self.total_profit = 0.0
        self.user_stats = {}
        self.blind_box_history = []  # 盲盒历史记录

        # 确保数据目录存在
        DATA_DIR.mkdir(exist_ok=True)

        # 当日数据文件路径
        self.current_data_date = date.today()

        self.init_ui()
        self.load_settings()
        self.load_data()  # 加载保存的数据

        # 定时检查日期变更（每分钟检查一次）
        self.date_check_timer = QTimer(self)
        self.date_check_timer.timeout.connect(self.check_date_change)
        self.date_check_timer.start(60000)  # 60秒检查一次

    def init_ui(self):
        """初始化UI"""
        self.setWindowTitle("B站直播间盲盒统计系统")
        self.setMinimumSize(1200, 800)  # 稍微大一点以适应直播展示

        # 主窗口部件
        main_widget = QWidget()
        self.setCentralWidget(main_widget)

        # 主布局
        main_layout = QVBoxLayout(main_widget)
        main_layout.setSpacing(8)  # 减小组件间距
        main_layout.setContentsMargins(8, 8, 8, 8)  # 减小边距

        # 配置区域
        config_group = QGroupBox("配置")
        config_layout = QHBoxLayout()

        config_layout.addWidget(QLabel("房间号:"))
        self.room_input = QLineEdit(DEFAULT_ROOM_ID)
        self.room_input.setFixedWidth(150)
        config_layout.addWidget(self.room_input)

        config_layout.addWidget(QLabel("Cookie:"))
        self.cookie_input = QLineEdit()
        self.cookie_input.setPlaceholderText("请输入B站Cookie...")
        config_layout.addWidget(self.cookie_input)

        self.start_btn = QPushButton("开始")
        self.start_btn.setFixedWidth(100)
        self.start_btn.clicked.connect(self.toggle_monitoring)
        config_layout.addWidget(self.start_btn)

        config_group.setLayout(config_layout)
        main_layout.addWidget(config_group)

        # 分割器
        splitter = QSplitter(Qt.Vertical)

        # 上半部分：统计面板
        stats_widget = QWidget()
        stats_layout = QVBoxLayout(stats_widget)

        # 统计卡片（紧凑版）
        cards_widget = QWidget()
        cards_layout = QHBoxLayout(cards_widget)
        cards_layout.setSpacing(8)  # 减小卡片间距

        # 盲盒数量
        count_card = self.create_stat_card("盲盒数量", "0", "个")
        self.count_label = count_card.findChild(QLabel, "value_label")
        cards_layout.addWidget(count_card)

        # 盈利盲盒
        profit_count_card = self.create_stat_card("盈利盲盒", "0", "个")
        self.profit_count_label = profit_count_card.findChild(QLabel, "value_label")
        cards_layout.addWidget(profit_count_card)

        # 亏损盲盒
        loss_count_card = self.create_stat_card("亏损盲盒", "0", "个")
        self.loss_count_label = loss_count_card.findChild(QLabel, "value_label")
        cards_layout.addWidget(loss_count_card)

        # 总盈亏
        profit_card = self.create_stat_card("总盈亏", "0.00", "元")
        self.profit_label = profit_card.findChild(QLabel, "value_label")
        cards_layout.addWidget(profit_card)

        stats_layout.addWidget(cards_widget)

        # 状态栏（紧凑版）
        self.status_label = QLabel("就绪")
        self.status_label.setStyleSheet("""
            color: #546E7A;
            padding: 6px 12px;
            font-size: 13px;
            background-color: #E3F2FD;
            border-radius: 6px;
            font-weight: 500;
            font-family: "Microsoft YaHei UI", "PingFang SC", sans-serif;
        """)
        stats_layout.addWidget(self.status_label)

        # 盲盒记录表格
        table_group = QGroupBox("盲盒记录")
        table_layout = QVBoxLayout()

        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["时间", "用户", "盲盒类型", "盈亏"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)

        # 设置表格不可编辑
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)

        # 设置表格行高和字体
        self.table.verticalHeader().setDefaultSectionSize(50)  # 行高50px
        table_layout.addWidget(self.table)

        table_group.setLayout(table_layout)
        stats_layout.addWidget(table_group)

        splitter.addWidget(stats_widget)

        # 下半部分：日志（直播时可隐藏）
        log_group = QGroupBox("运行日志")
        log_layout = QVBoxLayout()

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(80)  # 减小日志高度
        log_layout.addWidget(self.log_text)

        log_group.setLayout(log_layout)
        splitter.addWidget(log_group)

        splitter.setStretchFactor(0, 8)  # 表格占更大比例
        splitter.setStretchFactor(1, 1)

        main_layout.addWidget(splitter)

        # 样式设置 - 蓝色系现代简约设计
        self.setStyleSheet("""
            QMainWindow {
                background-color: #F0F4F8;
            }
            QGroupBox {
                font-weight: 600;
                border: none;
                border-radius: 8px;
                margin-top: 6px;
                padding-top: 20px;
                background-color: white;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                top: 6px;
                padding: 0 6px 0 6px;
                margin-top: 6px;
                color: #1976D2;
                font-size: 15px;
                font-family: "Microsoft YaHei UI", "PingFang SC", sans-serif;
            }
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                padding: 14px 28px;
                border-radius: 10px;
                font-weight: 600;
                font-size: 16px;
                font-family: "Microsoft YaHei UI", "PingFang SC", sans-serif;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
            QPushButton:pressed {
                background-color: #1565C0;
            }
            QLabel {
                color: #37474F;
                font-size: 15px;
                font-family: "Microsoft YaHei UI", "PingFang SC", sans-serif;
            }
            QLineEdit {
                padding: 14px;
                border: 2px solid #E3F2FD;
                border-radius: 10px;
                background-color: white;
                font-size: 15px;
                color: #37474F;
                font-family: "Microsoft YaHei UI", "PingFang SC", sans-serif;
            }
            QLineEdit:focus {
                border: 2px solid #2196F3;
            }
            QTableWidget {
                background-color: white;
                border: none;
                border-radius: 12px;
                gridline-color: #E3F2FD;
            }
            QTableWidget::item {
                padding: 18px;
                font-size: 18px;
                font-family: "Microsoft YaHei UI", "PingFang SC", sans-serif;
            }
            QTableWidget::item:selected {
                background-color: #E3F2FD;
            }
            QHeaderView::section {
                background-color: #F5F9FC;
                padding: 18px;
                border: none;
                border-bottom: 2px solid #E3F2FD;
                font-weight: 600;
                color: #1976D2;
                font-size: 18px;
                font-family: "Microsoft YaHei UI", "PingFang SC", sans-serif;
            }
            QTextEdit {
                background-color: #263238;
                color: #ECEFF1;
                border: none;
                border-radius: 12px;
                font-family: "Consolas", "JetBrains Mono", monospace;
                font-size: 14px;
                padding: 16px;
            }
        """)

    def create_stat_card(self, title: str, value: str, unit: str):
        """创建统计卡片 - 紧凑版适合直播"""
        card = QFrame()
        card.setFrameStyle(QFrame.StyledPanel)
        card.setStyleSheet("""
            QFrame {
                background-color: white;
                border-radius: 8px;
                padding: 12px;
                border: 1px solid #E3F2FD;
            }
        """)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(4)

        title_label = QLabel(title)
        title_label.setStyleSheet("""
            color: #1976D2;
            font-size: 13px;
            font-weight: 600;
            font-family: "Microsoft YaHei UI", "PingFang SC", sans-serif;
        """)
        layout.addWidget(title_label)

        value_layout = QHBoxLayout()
        value_label = QLabel(value)
        value_label.setObjectName("value_label")
        value_label.setStyleSheet("""
            font-size: 28px;
            font-weight: 700;
            color: #263238;
            font-family: "Segoe UI", "Roboto", "Microsoft YaHei UI", sans-serif;
        """)
        value_layout.addWidget(value_label)

        unit_label = QLabel(unit)
        unit_label.setStyleSheet("""
            color: #90A4AE;
            font-size: 18px;
            font-weight: 600;
            font-family: "Microsoft YaHei UI", "PingFang SC", sans-serif;
        """)
        value_layout.addWidget(unit_label)

        value_layout.addStretch()
        layout.addLayout(value_layout)

        return card

    def load_settings(self):
        """加载设置"""
        try:
            with open('gui_settings.json', 'r', encoding='utf-8') as f:
                settings = json.load(f)
                self.room_input.setText(settings.get('room_id', DEFAULT_ROOM_ID))
                self.cookie_input.setText(settings.get('cookie', ''))
        except:
            pass

    def save_settings(self):
        """保存设置"""
        try:
            with open('gui_settings.json', 'w', encoding='utf-8') as f:
                json.dump({
                    'room_id': self.room_input.text(),
                    'cookie': self.cookie_input.text()
                }, f, ensure_ascii=False, indent=2)
        except:
            pass

    def toggle_monitoring(self):
        """切换监听状态"""
        if self.listener_thread is None or not self.listener_thread.isRunning():
            self.start_monitoring()
        else:
            self.stop_monitoring()

    def start_monitoring(self):
        """开始监听"""
        room_id = self.room_input.text().strip()
        cookie = self.cookie_input.text().strip()

        if not room_id:
            QMessageBox.warning(self, "警告", "请输入房间号")
            return

        if not cookie:
            QMessageBox.warning(self, "警告", "请输入Cookie")
            return

        # 保存设置
        self.save_settings()

        # 不再重置统计数据，保持当日数据的连续性
        # 如果需要清空数据，可以手动删除 data/ 目录下的文件
        # self.blind_box_count = 0
        # self.profit_count = 0
        # self.loss_count = 0
        # self.total_profit = 0.0
        # self.user_stats = {}
        # self.table.setRowCount(0)

        # 更新UI
        self.update_stats_display()
        self.start_btn.setText("停止")
        self.start_btn.setStyleSheet("""
            QPushButton {
                background-color: #F44336;
                color: white;
                border: none;
                padding: 14px 28px;
                border-radius: 10px;
                font-weight: 600;
                font-size: 16px;
                font-family: "Microsoft YaHei UI", "PingFang SC", sans-serif;
            }
            QPushButton:hover {
                background-color: #D32F2F;
            }
        """)

        # 启动监听线程
        self.listener_thread = BlindBoxListenerThread(int(room_id), cookie)
        self.listener_thread.on_connected.connect(self.on_connected)
        self.listener_thread.on_error.connect(self.on_error)
        self.listener_thread.on_blind_box.connect(self.on_blind_box)
        self.listener_thread.on_status_update.connect(self.on_status_update)
        self.listener_thread.on_disconnected.connect(self.on_disconnected)
        self.listener_thread.start()

        self.log("开始监听...")

    def stop_monitoring(self):
        """停止监听"""
        if self.listener_thread:
            self.listener_thread.stop()
            self.listener_thread = None

        self.start_btn.setText("开始")
        self.start_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                padding: 14px 28px;
                border-radius: 10px;
                font-weight: 600;
                font-size: 16px;
                font-family: "Microsoft YaHei UI", "PingFang SC", sans-serif;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
        """)
        self.on_status_update("已停止")
        self.log("停止监听")

    def on_connected(self, room_title: str):
        """连接成功"""
        self.log(f"✓ 已连接到直播间: {room_title}")

    def on_error(self, error_msg: str):
        """错误处理"""
        self.log(f"✗ 错误: {error_msg}")
        QMessageBox.critical(self, "错误", error_msg)
        self.stop_monitoring()

    def on_blind_box(self, data: dict):
        """新盲盒数据"""
        self.blind_box_count += 1

        # 更新盈利/亏损计数
        if data['profit'] > 0:
            self.profit_count += 1
        elif data['profit'] < 0:
            self.loss_count += 1

        self.total_profit += data['profit']

        # 更新用户统计
        uid = data['uid']
        if uid not in self.user_stats:
            self.user_stats[uid] = {
                'uname': data['uname'],
                'count': 0,
                'cost': 0.0,
                'value': 0.0,
                'profit': 0.0
            }

        self.user_stats[uid]['count'] += 1
        self.user_stats[uid]['cost'] += data['cost']
        self.user_stats[uid]['value'] += data['value']
        self.user_stats[uid]['profit'] += data['profit']

        # 添加到历史记录
        self.blind_box_history.append(data)

        # 更新显示
        self.update_stats_display()
        self.add_table_row(data)

        # 自动保存数据
        self.save_data()

        # 日志
        profit_str = f"{data['profit']:+.2f}"
        self.log(f"[盲盒 #{self.blind_box_count}] {data['uname']} - {data['blind_name']}: {profit_str}元")

    def on_status_update(self, status: str):
        """状态更新"""
        self.status_label.setText(status)

    def on_disconnected(self):
        """断开连接"""
        self.start_btn.setText("开始")
        self.start_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                padding: 14px 28px;
                border-radius: 10px;
                font-weight: 600;
                font-size: 16px;
                font-family: "Microsoft YaHei UI", "PingFang SC", sans-serif;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
        """)
        self.log("连接已断开")

    def update_stats_display(self):
        """更新统计显示"""
        self.count_label.setText(str(self.blind_box_count))
        self.profit_count_label.setText(str(self.profit_count))
        self.loss_count_label.setText(str(self.loss_count))

        profit_str = f"{self.total_profit:+.2f}"
        self.profit_label.setText(profit_str)

        # 根据盈亏设置颜色 - 蓝色系配色
        if self.total_profit > 0:
            self.profit_label.setStyleSheet("""
                font-size: 28px;
                font-weight: 700;
                color: #4CAF50;
                font-family: "Segoe UI", "Roboto", "Microsoft YaHei UI", sans-serif;
            """)
        elif self.total_profit < 0:
            self.profit_label.setStyleSheet("""
                font-size: 28px;
                font-weight: 700;
                color: #F44336;
                font-family: "Segoe UI", "Roboto", "Microsoft YaHei UI", sans-serif;
            """)
        else:
            self.profit_label.setStyleSheet("""
                font-size: 28px;
                font-weight: 700;
                color: #263238;
                font-family: "Segoe UI", "Roboto", "Microsoft YaHei UI", sans-serif;
            """)

    def add_table_row(self, data: dict):
        """添加表格行（插入到顶部以便直播观看）"""
        self.table.insertRow(0)  # 在顶部插入新行

        # 时间
        self.table.setItem(0, 0, QTableWidgetItem(data['time']))

        # 用户
        self.table.setItem(0, 1, QTableWidgetItem(data['uname']))

        # 盲盒类型
        blind_name_item = QTableWidgetItem(data['blind_name'])
        # 根据盈亏给盲盒类型设置颜色 - 蓝色系方案
        if data['profit'] >= 40:
            blind_name_item.setForeground(QBrush(QColor(255, 193, 7)))  # 金色 - 大奖
        elif data['profit'] > 0:
            blind_name_item.setForeground(QBrush(QColor(76, 175, 80)))  # 绿色 - 小奖
        elif data['profit'] <= -20:
            blind_name_item.setForeground(QBrush(QColor(156, 39, 176)))  # 紫色 - 深度亏损
        else:
            blind_name_item.setForeground(QBrush(QColor(244, 67, 54)))  # 红色 - 普通亏损
        self.table.setItem(0, 2, blind_name_item)

        # 盈亏
        profit_item = QTableWidgetItem(f"{data['profit']:+.2f}元")
        if data['profit'] > 0:
            profit_item.setForeground(QBrush(QColor(76, 175, 80)))  # 绿色 - 盈利
        elif data['profit'] < 0:
            profit_item.setForeground(QBrush(QColor(244, 67, 54)))  # 红色 - 亏损
        self.table.setItem(0, 3, profit_item)

        # 滚动到顶部查看最新记录
        self.table.scrollToTop()

        # 限制行数，移除最旧的记录
        if self.table.rowCount() > 100:
            self.table.removeRow(100)

    def log(self, message: str):
        """输出日志"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.append(f"[{timestamp}] {message}")

    def check_date_change(self):
        """检查日期是否变更"""
        today = date.today()
        if today != self.current_data_date:
            # 日期已变更，保存旧数据并初始化新数据
            self.log(f"日期已变更，保存 {self.current_data_date} 的数据")
            self.save_data()

            # 重置统计数据
            self.current_data_date = today
            self.blind_box_count = 0
            self.profit_count = 0
            self.loss_count = 0
            self.total_profit = 0.0
            self.user_stats = {}
            self.blind_box_history = []
            self.table.setRowCount(0)

            self.update_stats_display()
            self.log(f"新的一天开始！数据已重置")

    def save_data(self):
        """保存数据到文件"""
        try:
            data = {
                'date': self.current_data_date.isoformat(),
                'blind_box_count': self.blind_box_count,
                'profit_count': self.profit_count,
                'loss_count': self.loss_count,
                'total_profit': self.total_profit,
                'user_stats': self.user_stats,
                'blind_box_history': self.blind_box_history
            }

            # 使用当前日期的数据文件
            data_file = DATA_DIR / f"blind_box_data_{self.current_data_date.isoformat()}.json"

            with open(data_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            print(f"[保存] 数据已保存到 {data_file}")
        except Exception as e:
            print(f"[错误] 保存数据失败: {e}")

    def load_data(self):
        """从文件加载数据"""
        try:
            # 使用当日的数据文件
            data_file = DATA_DIR / f"blind_box_data_{date.today().isoformat()}.json"

            if not data_file.exists():
                print(f"[提示] 未找到今日数据文件，从空白开始")
                return

            with open(data_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # 检查日期是否匹配（防止跨天问题）
            if data.get('date') != date.today().isoformat():
                print(f"[提示] 数据文件日期不匹配，创建新记录")
                return

            # 加载数据
            self.blind_box_count = data.get('blind_box_count', 0)
            self.profit_count = data.get('profit_count', 0)
            self.loss_count = data.get('loss_count', 0)
            self.total_profit = data.get('total_profit', 0.0)
            self.user_stats = data.get('user_stats', {})
            self.blind_box_history = data.get('blind_box_history', [])

            # 恢复表格显示
            self.restore_table_from_history()

            # 更新统计显示
            self.update_stats_display()

            print(f"[加载] 数据已加载，共 {self.blind_box_count} 个盲盒记录")
        except Exception as e:
            print(f"[错误] 加载数据失败: {e}")

    def restore_table_from_history(self):
        """从历史记录恢复表格"""
        # 清空表格
        self.table.setRowCount(0)

        # 恢复最近100条记录
        recent_records = self.blind_box_history[-100:] if len(self.blind_box_history) > 100 else self.blind_box_history

        for record in reversed(recent_records):  # 倒序插入，最新的在最上面
            self.add_table_row(record)

    def closeEvent(self, event):
        """关闭事件"""
        if self.listener_thread:
            self.listener_thread.stop()

        # 保存数据
        self.save_data()

        event.accept()


# ==================== 主程序入口 ====================

def main():
    import warnings
    warnings.filterwarnings("ignore", category=Warning)

    app = QApplication(sys.argv)
    app.setStyle('Fusion')

    window = BlindBoxStatsWindow()
    window.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
