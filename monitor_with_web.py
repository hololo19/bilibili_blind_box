#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
B站直播间盲盒盈亏统计工具 - Web集成版本
监听盲盒并自动推送到Web服务器
"""

import asyncio
import json
import struct
import zlib
import brotli
import time
import requests
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import aiohttp
import hashlib
import urllib.parse
import re
import sys

#
sys.stdout.reconfigure(line_buffering=True)

# ==================== 配置区域 ====================
import os
from pathlib import Path

# 尝试从配置文件加载配置
DATA_DIR = Path(__file__).parent / "data"
CONFIG_FILE = DATA_DIR / "monitor_temp_config.json"

ROOM_ID = 24872476
COOKIE = ""
WEB_SERVER_URL = "http://localhost:5000"

if CONFIG_FILE.exists():
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            config = json.load(f)
            ROOM_ID = config.get("ROOM_ID", ROOM_ID)
            COOKIE = config.get("COOKIE", COOKIE)
            WEB_SERVER_URL = config.get("WEB_SERVER_URL", WEB_SERVER_URL)
            print(f"[配置] 已从配置文件加载：房间号 {ROOM_ID}")
    except Exception as e:
        print(f"[错误] 加载配置文件失败: {e}")
else:
    print("[提示] 未找到配置文件，使用默认配置")

# =================================================

MIXIN_KEY_ENC_TAB = [
    46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35, 27, 43, 5, 49,
    33, 9, 42, 19, 29, 28, 14, 39, 12, 38, 41, 13, 37, 48, 7, 16, 24, 55, 40,
    61, 26, 17, 0, 1, 60, 51, 30, 4, 22, 25, 54, 21, 56, 59, 6, 63, 57, 62, 11,
    36, 20, 34, 44, 52
]


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


async def get_real_room_id(room_id: int, headers: dict) -> Tuple[Optional[int], Optional[str]]:
    """获取真实房间号和房间标题"""
    url = "https://api.live.bilibili.com/xlive/web-room/v1/index/getInfoByRoom"
    params = {"room_id": room_id}

    uncompressed_headers = headers.copy()
    uncompressed_headers['Accept-Encoding'] = 'gzip'

    async with aiohttp.ClientSession() as session:
        try:
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

    async with aiohttp.ClientSession() as session:
        try:
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

    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(full_url, headers=uncompressed_headers, compress=False) as resp:
                data = await resp.json()
                if resp.status == 200 and data['code'] == 0:
                    return data['data'], real_room_id, room_title
        except Exception:
            pass
    return None, None, None


def extract_uid_from_cookie(cookie: str) -> int:
    """从Cookie中提取DedeUserID"""
    match = re.search(r'DedeUserID=(\d+)', cookie)
    if match:
        return int(match.group(1))
    return 0


def send_to_web_server(uid: int, uname: str, gift_name: str,
                      blind_price: int, gift_price: int):
    """发送盲盒数据到Web服务器 - 修复字段映射"""
    try:
        requests.post(
            f"{WEB_SERVER_URL}/api/blind_box",
            json={
                'uid': uid,
                'uname': uname,
                'blind_name': gift_name,  # 修正：gift_name实际是盲盒名称
                'blind_price': blind_price,
                'gift_price': gift_price
            },
            timeout=1
        )
    except:
        pass  # 静默失败，不影响监听


async def main():
    """主函数"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Referer': 'https://live.bilibili.com/',
        'Cookie': COOKIE,
        'Accept-Encoding': 'gzip'
    }

    user_id = extract_uid_from_cookie(COOKIE)

    print(f"\n{'='*60}")
    print(f"盲盒监听启动 - 直播间: {ROOM_ID}")
    print(f"Web服务器: {WEB_SERVER_URL}")
    print(f"{'='*60}\n")

    # 测试Web服务器连接
    try:
        response = requests.get(f"{WEB_SERVER_URL}/api/stats", timeout=2)
        if response.status_code == 200:
            print(f"[OK] Web服务器连接成功\n")
        else:
            print(f"[WARNING] Web服务器响应异常\n")
    except:
        print(f"[WARNING] 无法连接到Web服务器，请确保web_server.py正在运行\n")

    danmu_info, real_room_id, room_title = await get_danmu_info(ROOM_ID, headers)
    if not danmu_info or not real_room_id:
        print("[ERROR] 获取房间信息失败")
        return

    host_info = danmu_info['host_list'][0]
    ws_url = f"wss://{host_info['host']}:{host_info['wss_port']}/sub"
    token = danmu_info['token']

    try:
        async with aiohttp.ClientSession() as session:
            async with session.ws_connect(ws_url) as ws:
                await asyncio.sleep(0.5)
                if ws.closed:
                    print("[ERROR] WebSocket连接已关闭")
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
                if ws.closed:
                    print("[ERROR] 认证后连接已关闭")
                    return

                print(f"[OK] 连接成功，开始监听...\n")
                print(f"[提示] 打开浏览器访问 http://localhost:5000 查看实时数据\n")

                heartbeat_task = asyncio.create_task(heartbeat(ws))
                message_task = asyncio.create_task(message_listener(ws))

                done, pending = await asyncio.wait(
                    [heartbeat_task, message_task],
                    return_when=asyncio.FIRST_COMPLETED
                )

                for task in pending:
                    task.cancel()

    except Exception as e:
        print(f"[ERROR] {e}")
    finally:
        print("\n[INFO] 程序退出")


async def heartbeat(ws):
    """心跳任务"""
    try:
        while not ws.closed:
            await asyncio.sleep(30)
            if ws.closed:
                break
            await ws.send_bytes(encode_packet(b'', 2))
    except asyncio.CancelledError:
        pass
    except Exception:
        pass


async def message_listener(ws):
    """消息监听任务"""
    count = 0

    try:
        while not ws.closed:
            try:
                msg = await asyncio.wait_for(ws.receive(), timeout=30)

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
                                                count += 1
                                                uid = data.get('uid', 0)
                                                uname = data.get('uname', '未知')
                                                # 修正：盲盒名称在 blind_gift.original_gift_name
                                                gift_name = blind_gift.get('original_gift_name', '未知')
                                                blind_price = blind_gift.get('original_gift_price', 0)
                                                gift_price = blind_gift.get('gift_tip_price', 0)

                                                # 显示终端输出
                                                profit = (gift_price - blind_price) / 1000
                                                print(f"[盲盒 #{count}] {uname} - {gift_name}: {profit:+.2f}元")

                                                # 发送到Web服务器
                                                send_to_web_server(
                                                    uid, uname, gift_name,
                                                    blind_price, gift_price
                                                )

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
        print(f"\n[统计] 共捕获 {count} 个盲盒")
    except Exception:
        pass


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n[STOP] 用户中断")
