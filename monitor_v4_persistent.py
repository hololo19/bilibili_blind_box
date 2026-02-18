#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
B站直播间盲盒盈亏统计工具 - 持久化版本
"""

import asyncio
import json
import struct
import zlib
import brotli
import time
from typing import Dict, List, Optional, Tuple
import aiohttp
import hashlib
import urllib.parse
import re
import sys
from datetime import datetime
from collections import defaultdict
import os

# 确保输出不被缓冲
sys.stdout.reconfigure(line_buffering=True)

# ==================== 配置区域 ====================
ROOM_ID = 24872476
COOKIE = "buvid3=C3AE6C7D-7D68-60A7-B11F-33B2E1CAB44C88526infoc; b_nut=1758030288; _uuid=410F9718F-96EA-C8E10-6AC7-49CC4C57BD6B89094infoc; enable_web_push=DISABLE; buvid4=37C73D9C-A390-8A12-65C5-9BF1BBCB23D989172-025091621-2+Ib7CxdazXm9KE1TnSNcs5iR1xHLghjLEW06uOfx8Y%3D; hit-dyn-v2=1; theme-tip-show=SHOWED; LIVE_BUVID=AUTO2117580323118353; theme-avatar-tip-show=SHOWED; rpdid=0zbfVJBNQA|4ZIEPP2g|2s|3w1UZ4j6; CURRENT_QUALITY=80; dy_spec_agreed=1; fingerprint=04182de32636857702b9f27292062e7d; buvid_fp_plain=undefined; buvid_fp=04182de32636857702b9f27292062e7d; theme-switch-show=SHOWED; PVID=21; bili_ticket=eyJhbGciOiJIUzI1NiIsImtpZCI6InMwMyIsInR5cCI6IkpXVCJ9.eyJleHAiOjE3NzE0MTAwMzIsImlhdCI6MTc3MTE1MDc3MiwicGx0IjotMX0.xDaZXZEXPhzJXfgDJNHvo3bxOs0xZxmXvg-foNmy8mg; bili_ticket_expires=1771409972; bmg_af_switch=1; bmg_src_def_domain=i1.hdslb.com; bp_t_offset_3691002128763414=1169573784303173632; CURRENT_FNVAL=2000; bp_t_offset_37884462=1169574720606044160; mp_851392464b60e8cc1948a193642f793b_mixpanel=%7B%22distinct_id%22%3A%20%22%24device%3A199510de70c36f-0f70823355071f-4c657b58-190140-199510de70c36f%22%2C%22%24device_id%22%3A%20%22199510de70c36f-0f70823355071f-4c657b58-190140-199510de70c36f%22%2C%22%24search_engine%22%3A%20%22bing%22%2C%22%24initial_referrer%22%3A%20%22https%3A%2F%2Fcn.bing.com%2F%22%2C%22%24initial_referring_domain%22%3A%20%22cn.bing.com%22%7D; SESSDATA=49744543%2C1786703258%2C92737%2A22CjB_6pmoSTgu0wzzY0MF7ZcTm8FlK1TlLYOF-AGKDWdKY29zjhwxOFccq6iQejsIsOcSVnlDa0RqZDN6Y0dmanBJMnFfdE1BS3hxbGNTWldjOEdlNTVZenNsb2ljcFMxMFFwT1JRU05Qc0FaZVhycXVUcERDQlpicG5vN2t2VDM2b0ZtSGwzYWdRIIEC; bili_jct=82509a543d31218190a97be7d21354bc; DedeUserID=3691002128763414; DedeUserID__ckMd5=d26dea7ae761365f; sid=5316moqx; home_feed_column=4; browser_resolution=684-868; b_lsid=A477237B_19C60D7CA13"

# 数据保存文件
DATA_FILE = "blind_box_data.json"

# 自动保存间隔（秒）
AUTO_SAVE_INTERVAL = 60
# 显示排行榜间隔（秒）
RANKING_DISPLAY_INTERVAL = 300
# =================================================

MIXIN_KEY_ENC_TAB = [
    46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35, 27, 43, 5, 49,
    33, 9, 42, 19, 29, 28, 14, 39, 12, 38, 41, 13, 37, 48, 7, 16, 24, 55, 40,
    61, 26, 17, 0, 1, 60, 51, 30, 4, 22, 25, 54, 21, 56, 59, 6, 63, 57, 62, 11,
    36, 20, 34, 44, 52
]

# 全局统计数据
user_stats = {}  # {uid: {uname, count, cost, value, profit, history}}
total_stats = {"count": 0, "cost": 0, "value": 0, "profit": 0}


class BlindBoxTracker:
    """盲盒统计追踪器"""

    def __init__(self):
        self.last_ranking_display = 0
        self.last_save = 0

    def add_blind_box(self, uid: int, uname: str, gift_name: str,
                     blind_price: int, gift_price: int):
        """添加盲盒记录"""
        global user_stats, total_stats

        profit = (gift_price - blind_price) / 1000
        blind_price_yuan = blind_price / 1000
        gift_price_yuan = gift_price / 1000

        # 更新用户统计
        if uid not in user_stats:
            user_stats[uid] = {
                "uid": uid,
                "uname": uname,
                "count": 0,
                "cost": 0,
                "value": 0,
                "profit": 0,
                "history": []
            }

        user_stats[uid]["count"] += 1
        user_stats[uid]["cost"] += blind_price
        user_stats[uid]["value"] += gift_price
        user_stats[uid]["profit"] += profit
        user_stats[uid]["history"].append({
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "blind_name": gift_name,
            "cost": blind_price_yuan,
            "value": gift_price_yuan,
            "profit": profit
        })

        # 更新总体统计
        total_stats["count"] += 1
        total_stats["cost"] += blind_price
        total_stats["value"] += gift_price
        total_stats["profit"] += profit

        # 显示单次盲盒结果
        self.display_single_record(uname, gift_name, blind_price_yuan, gift_price_yuan, profit)

        # 显示用户累计统计
        self.display_user_stats(uid)

    def display_single_record(self, uname: str, blind_name: str,
                             cost: float, value: float, profit: float):
        """显示单次盲盒记录"""
        print(f"\n{'='*60}")
        print(f"[盲盒记录]")
        print(f"{'='*60}")
        print(f"发送者: {uname}")
        print(f"盲盒名称: {blind_name}")
        print(f"盲盒价格: {cost:.2f} 元")
        print(f"爆出价值: {value:.2f} 元")
        print(f"本次盈亏: {profit:+.2f} 元")
        print(f"{'='*60}\n")

    def display_user_stats(self, uid: int):
        """显示用户累计统计"""
        if uid not in user_stats:
            return

        stats = user_stats[uid]
        print(f"[累计统计] {stats['uname']}: 已送{stats['count']}个盲盒, "
              f"总花费{stats['cost']/1000:.2f}元, 总价值{stats['value']/1000:.2f}元, "
              f"总盈亏{stats['profit']:+.2f}元\n")

    def display_ranking(self, top_n: int = 10):
        """显示排行榜"""
        print(f"\n{'='*60}")
        print(f"[盲盒排行榜 TOP {top_n}]")
        print(f"{'='*60}")

        # 按盲盒数量排序
        sorted_users = sorted(user_stats.values(),
                            key=lambda x: x["count"],
                            reverse=True)[:top_n]

        for i, user in enumerate(sorted_users, 1):
            print(f"{i}. {user['uname']}")
            print(f"   盲盒数: {user['count']}个")
            print(f"   总花费: {user['cost']/1000:.2f}元")
            print(f"   总价值: {user['value']/1000:.2f}元")
            print(f"   总盈亏: {user['profit']:+.2f}元")
            print()

        # 显示总体统计
        print(f"[总体统计]")
        print(f"总盲盒数: {total_stats['count']}个")
        print(f"总花费: {total_stats['cost']/1000:.2f}元")
        print(f"总价值: {total_stats['value']/1000:.2f}元")
        print(f"总盈亏: {total_stats['profit']:+.2f}元")
        print(f"{'='*60}\n")

    def save_to_file(self):
        """保存数据到文件"""
        data = {
            "user_stats": user_stats,
            "total_stats": total_stats,
            "last_update": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        try:
            with open(DATA_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[ERROR] 保存数据失败: {e}")

    def load_from_file(self):
        """从文件加载数据"""
        global user_stats, total_stats
        if not os.path.exists(DATA_FILE):
            return

        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                user_stats = data.get("user_stats", {})
                total_stats = data.get("total_stats",
                    {"count": 0, "cost": 0, "value": 0, "profit": 0})
            print(f"[INFO] 已加载历史数据，共{len(user_stats)}位用户，"
                  f"{total_stats['count']}个盲盒记录\n")
        except Exception as e:
            print(f"[ERROR] 加载数据失败: {e}")


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


async def main():
    """主函数"""
    tracker = BlindBoxTracker()
    tracker.load_from_file()

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Referer': 'https://live.bilibili.com/',
        'Cookie': COOKIE,
        'Accept-Encoding': 'gzip'
    }

    user_id = extract_uid_from_cookie(COOKIE)

    print(f"\n{'='*60}")
    print(f"盲盒监听启动 - 直播间: {ROOM_ID}")
    print(f"{'='*60}\n")

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

                heartbeat_task = asyncio.create_task(heartbeat(ws))
                message_task = asyncio.create_task(message_listener(ws, tracker))

                done, pending = await asyncio.wait(
                    [heartbeat_task, message_task],
                    return_when=asyncio.FIRST_COMPLETED
                )

                for task in pending:
                    task.cancel()

    except Exception as e:
        print(f"[ERROR] {e}")
    finally:
        tracker.save_to_file()
        print("\n[INFO] 数据已保存，程序退出")


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


async def message_listener(ws, tracker: BlindBoxTracker):
    """消息监听任务"""
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
                                                uid = data.get('uid', 0)
                                                uname = data.get('uname', '未知')
                                                gift_name = data.get('gift_name', '未知')
                                                blind_price = blind_gift.get('original_gift_price', 0)
                                                gift_price = blind_gift.get('gift_tip_price', 0)

                                                # 添加到统计
                                                tracker.add_blind_box(
                                                    uid, uname, gift_name,
                                                    blind_price, gift_price
                                                )

                                                # 定期保存
                                                current_time = time.time()
                                                if current_time - tracker.last_save >= AUTO_SAVE_INTERVAL:
                                                    tracker.save_to_file()
                                                    tracker.last_save = current_time
                                                    print("[INFO] 数据已自动保存\n")

                                                # 定期显示排行榜
                                                if current_time - tracker.last_ranking_display >= RANKING_DISPLAY_INTERVAL:
                                                    tracker.display_ranking()
                                                    tracker.last_ranking_display = current_time

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
        tracker.display_ranking()
    except Exception:
        pass


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n[STOP] 用户中断")
