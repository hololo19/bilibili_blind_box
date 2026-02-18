#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
盲盒统计Web服务器 - 增强版
支持按日期保存、Web控制监听器
"""

from flask import Flask, render_template, jsonify, request
from flask_socketio import SocketIO, emit
import json
import os
from datetime import datetime, date
import threading
import time
import subprocess
import signal

app = Flask(__name__)
app.config['SECRET_KEY'] = 'blind_box_secret_key_2024'
socketio = SocketIO(app, cors_allowed_origins="*")

# 数据目录和文件
DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')
os.makedirs(DATA_DIR, exist_ok=True)

# 当前日期的数据文件
CURRENT_DATA_FILE = os.path.join(DATA_DIR, f"blind_box_data_{date.today().isoformat()}.json")

MAX_RECENT_RECORDS = 500  # 增加到500条记录
MAX_USER_HISTORY = 1000   # 每个用户最多保存1000条历史

user_stats = {}
total_stats = {"count": 0, "cost": 0, "value": 0, "profit": 0, "profit_count": 0, "loss_count": 0}
recent_records = []  # 保存最近的记录

# 监听器进程控制
monitor_process = None
monitor_config = {
    "room_id": "",
    "cookie": "",
    "is_running": False
}


class BlindBoxTracker:
    """盲盒统计追踪器"""

    def __init__(self):
        self.load_from_file()

    def add_blind_box(self, uid: int, uname: str, blind_name: str,
                     blind_price: int, gift_price: int):
        """添加盲盒记录 - 修复字段名称"""
        global user_stats, total_stats, recent_records

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

        # 添加历史记录，限制数量
        user_stats[uid]["history"].append({
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "blind_name": blind_name,
            "cost": blind_price_yuan,
            "value": gift_price_yuan,
            "profit": profit
        })

        # 限制用户历史记录数量
        if len(user_stats[uid]["history"]) > MAX_USER_HISTORY:
            user_stats[uid]["history"] = user_stats[uid]["history"][-MAX_USER_HISTORY:]

        # 更新总体统计
        total_stats["count"] += 1
        total_stats["cost"] += blind_price
        total_stats["value"] += gift_price
        total_stats["profit"] += profit

        # 更新盈利/亏损计数
        if profit > 0:
            total_stats["profit_count"] = total_stats.get("profit_count", 0) + 1
        elif profit < 0:
            total_stats["loss_count"] = total_stats.get("loss_count", 0) + 1

        # 添加到最近记录 - 使用正确的字段名
        record = {
            "time": datetime.now().strftime("%H:%M:%S"),
            "uname": uname,
            "blind_name": blind_name,  # 修复：使用盲盒名称而不是爆出礼物名称
            "cost": blind_price_yuan,
            "value": gift_price_yuan,
            "profit": profit
        }
        recent_records.insert(0, record)

        # 限制最近记录数量，但保留更多
        if len(recent_records) > MAX_RECENT_RECORDS:
            recent_records.pop()

        # 通过WebSocket推送新记录
        socketio.emit('new_blind_box', record)

        # 通过WebSocket推送统计更新
        # 计算盈亏分布
        profit_dist = {'profit': 0, 'loss': 0, 'break_even': 0}
        for user in user_stats.values():
            for record in user.get("history", []):
                if record["profit"] > 0:
                    profit_dist['profit'] += 1
                elif record["profit"] < 0:
                    profit_dist['loss'] += 1
                else:
                    profit_dist['break_even'] += 1

        socketio.emit('stats_update', {
            'total': total_stats,
            'user_count': len(user_stats),
            'profit_distribution': profit_dist
        })

    def save_to_file(self):
        """保存数据到文件"""
        data = {
            "date": date.today().isoformat(),
            "user_stats": user_stats,
            "total_stats": total_stats,
            "last_update": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        try:
            # 使用当前日期的文件
            data_file = os.path.join(DATA_DIR, f"blind_box_data_{date.today().isoformat()}.json")
            with open(data_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"[保存] 数据已保存到 {data_file}")
        except Exception as e:
            print(f"[ERROR] 保存数据失败: {e}")

    def load_from_file(self):
        """从文件加载数据"""
        global user_stats, total_stats

        # 使用当前日期的文件
        data_file = os.path.join(DATA_DIR, f"blind_box_data_{date.today().isoformat()}.json")

        if not os.path.exists(data_file):
            print(f"[提示] 未找到今日数据文件，从空白开始")
            return

        try:
            with open(data_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

                # 检查日期是否匹配
                if data.get("date") != date.today().isoformat():
                    print(f"[提示] 数据文件日期不匹配，创建新记录")
                    return

                loaded_stats = data.get("user_stats", {})

                # 修复：JSON中的uid会被转为字符串，需要转回整数
                user_stats = {}
                for uid_str, user_data in loaded_stats.items():
                    try:
                        uid = int(uid_str)
                        user_stats[uid] = user_data
                    except ValueError:
                        # 如果不是数字，保持原样
                        user_stats[uid_str] = user_data

                total_stats = data.get("total_stats",
                    {"count": 0, "cost": 0, "value": 0, "profit": 0, "profit_count": 0, "loss_count": 0})

                # 兼容旧版本数据格式（包含cost/value但没有profit_count/loss_count）
                if "cost" in total_stats and "profit_count" not in total_stats:
                    # 旧格式，添加新字段
                    total_stats["profit_count"] = 0
                    total_stats["loss_count"] = 0

            # 限制历史记录大小，防止数据过大
            for uid in user_stats:
                if len(user_stats[uid].get("history", [])) > MAX_USER_HISTORY:
                    user_stats[uid]["history"] = user_stats[uid]["history"][-MAX_USER_HISTORY:]

            print(f"[加载] 已加载今日数据，共{len(user_stats)}位用户，"
                  f"{total_stats['count']}个盲盒记录")
        except Exception as e:
            print(f"[ERROR] 加载数据失败: {e}")


tracker = BlindBoxTracker()

# 加载监听器配置
config_file = os.path.join(DATA_DIR, "monitor_config.json")
if os.path.exists(config_file):
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            monitor_config.update(json.load(f))
    except Exception as e:
        print(f"[ERROR] 加载监听器配置失败: {e}")


# ==================== 路由 ====================

@app.route('/')
def index():
    """主页"""
    return render_template('index.html')


@app.route('/api/stats')
def get_stats():
    """获取统计数据 - 包含盈亏分布"""
    # 计算盈亏分布和总统计数据
    profit_count = 0
    loss_count = 0
    break_even_count = 0
    total_cost = 0
    total_value = 0

    for uid, user in user_stats.items():
        total_cost += user.get("cost", 0)
        total_value += user.get("value", 0)
        for record in user.get("history", []):
            if record["profit"] > 0:
                profit_count += 1
            elif record["profit"] < 0:
                loss_count += 1
            else:
                break_even_count += 1

    # 重新计算总盈亏
    total_profit = (total_value - total_cost) / 1000  # 转换为元

    # 更新 total_stats 确保数据一致
    total_stats["count"] = sum(user.get("count", 0) for user in user_stats.values())
    total_stats["cost"] = total_cost
    total_stats["value"] = total_value
    total_stats["profit"] = total_profit
    total_stats["profit_count"] = profit_count
    total_stats["loss_count"] = loss_count

    # 收集所有历史记录用于翻页
    all_history = []
    for uid, user in user_stats.items():
        uname = user.get("uname", "未知")
        for record in user.get("history", []):
            all_history.append({
                "time": record["time"],
                "uname": uname,
                "blind_name": record["blind_name"],
                "value": record["value"],
                "profit": record["profit"]
            })

    # 按时间倒序排序
    all_history.sort(key=lambda x: x["time"], reverse=True)

    return jsonify({
        'total': total_stats,
        'user_count': len(user_stats),
        'recent': all_history[:500],  # 返回更多历史记录
        'profit_distribution': {
            'profit': profit_count,
            'loss': loss_count,
            'break_even': break_even_count
        }
    })


@app.route('/api/ranking')
def get_ranking():
    """获取排行榜 - 按运气排序"""
    MIN_BLIND_BOXES = 1  # 最少盲盒数要求

    # 过滤出至少送了MIN_BLIND_BOXES个盲盒的用户
    qualified_users = [u for u in user_stats.values() if u["count"] >= MIN_BLIND_BOXES]

    # 计算每个用户的运气指标
    for user in qualified_users:
        cost = user["cost"]
        value = user["value"]

        # 盈亏率（百分比）
        if cost > 0:
            user["profit_rate"] = (value - cost) / cost * 100
        else:
            user["profit_rate"] = 0

        # 总盈亏
        user["total_profit"] = user["profit"]

    # 按盈亏率排序（盈亏率高的运气好）
    # 次要排序：盲盒数量（相同样本数下，送更多的优先）
    sorted_users = sorted(qualified_users,
                         key=lambda x: (x["profit_rate"], x["count"]),
                         reverse=True)  # 移除数量限制，显示全部用户

    ranking = []
    for user in sorted_users:
        ranking.append({
            'uname': user['uname'],
            'count': user['count'],
            'cost': user['cost'] / 1000,
            'value': user['value'] / 1000,
            'profit': user['profit'],
            'profit_rate': user['profit_rate']
        })

    return jsonify(ranking)


@app.route('/api/users')
def get_users():
    """获取所有用户列表"""
    users = []
    for uid, user in user_stats.items():
        users.append({
            'uid': uid,
            'uname': user['uname'],
            'count': user['count'],
            'cost': user['cost'] / 1000,
            'value': user['value'] / 1000,
            'profit': user['profit']
        })
    return jsonify(users)


@app.route('/api/blind_box', methods=['POST'])
def add_blind_box():
    """接收盲盒数据 - 修复字段映射"""
    data = request.json

    # 修正字段名：从gift_name改为blind_name
    tracker.add_blind_box(
        uid=data.get('uid', 0),
        uname=data.get('uname', '未知'),
        blind_name=data.get('blind_name', data.get('gift_name', '未知')),  # 兼容处理
        blind_price=data.get('blind_price', 0),
        gift_price=data.get('gift_price', 0)
    )
    return jsonify({'status': 'success'})


# ==================== 监听器控制API ====================

@app.route('/api/config', methods=['GET', 'POST'])
def handle_monitor_config():
    """获取或设置监听器配置"""
    global monitor_config

    if request.method == 'POST':
        data = request.json
        monitor_config['room_id'] = data.get('room_id', '')
        monitor_config['cookie'] = data.get('cookie', '')

        # 保存配置到文件
        try:
            config_file = os.path.join(DATA_DIR, "monitor_config.json")
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(monitor_config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[ERROR] 保存配置失败: {e}")

        return jsonify({'status': 'success', 'config': monitor_config})

    return jsonify(monitor_config)


@app.route('/api/monitor/start', methods=['POST'])
def start_monitor():
    """启动监听器"""
    global monitor_process, monitor_config

    if monitor_config['is_running']:
        return jsonify({'status': 'error', 'message': '监听器已在运行'})

    if not monitor_config['room_id'] or not monitor_config['cookie']:
        return jsonify({'status': 'error', 'message': '请先配置房间号和Cookie'})

    try:
        # 创建临时配置文件
        temp_config = {
            "ROOM_ID": int(monitor_config['room_id']),
            "COOKIE": monitor_config['cookie'],
            "WEB_SERVER_URL": "http://localhost:5000"
        }

        config_file = os.path.join(DATA_DIR, "monitor_temp_config.json")
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(temp_config, f, ensure_ascii=False, indent=2)

        # 启动monitor_with_web.py进程
        import sys
        script_path = os.path.join(os.path.dirname(__file__), 'monitor_with_web.py')

        # 使用subprocess启动监听器
        monitor_process = subprocess.Popen(
            [sys.executable, script_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=os.path.dirname(__file__)
        )

        monitor_config['is_running'] = True

        # 通过WebSocket通知所有客户端
        socketio.emit('monitor_status', {'running': True})

        return jsonify({'status': 'success', 'message': '监听器已启动'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': f'启动失败: {str(e)}'})


@app.route('/api/monitor/stop', methods=['POST'])
def stop_monitor():
    """停止监听器"""
    global monitor_process, monitor_config

    if not monitor_config['is_running']:
        return jsonify({'status': 'error', 'message': '监听器未运行'})

    try:
        if monitor_process:
            monitor_process.terminate()
            monitor_process.wait(timeout=5)
            monitor_process = None

        monitor_config['is_running'] = False

        # 通过WebSocket通知所有客户端
        socketio.emit('monitor_status', {'running': False})

        return jsonify({'status': 'success', 'message': '监听器已停止'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': f'停止失败: {str(e)}'})


@app.route('/api/monitor/status', methods=['GET'])
def monitor_status():
    """获取监听器状态"""
    return jsonify({
        'running': monitor_config['is_running'],
        'room_id': monitor_config['room_id']
    })


# ==================== WebSocket事件 ====================

@socketio.on('connect')
def handle_connect():
    """客户端连接"""
    emit('stats_update', {
        'total': total_stats,
        'user_count': len(user_stats)
    })
    emit('recent_records', recent_records[:20])


@socketio.on('disconnect')
def handle_disconnect():
    """客户端断开"""
    pass


# ==================== 自动保存 ====================

def auto_save():
    """自动保存线程"""
    while True:
        time.sleep(60)
        tracker.save_to_file()
        print(f"[INFO] 数据已自动保存")


save_thread = threading.Thread(target=auto_save, daemon=True)
save_thread.start()


if __name__ == '__main__':
    print("\n" + "="*60)
    print("盲盒统计Web服务器启动")
    print("="*60)
    print(f"访问地址: http://localhost:5000")
    print(f"数据文件: {CURRENT_DATA_FILE}")
    print(f"最大记录数: {MAX_RECENT_RECORDS}")
    print("="*60 + "\n")

    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
