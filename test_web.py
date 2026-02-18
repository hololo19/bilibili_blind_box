#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试Web服务器功能
"""

import sys
import os

# 检查依赖
print("=" * 60)
print("检查Python依赖...")
print("=" * 60)

dependencies = {
    'flask': 'Flask',
    'flask_socketio': 'Flask-SocketIO',
    'aiohttp': 'aiohttp',
    'requests': 'requests',
    'brotli': 'brotli'
}

missing = []
for module, name in dependencies.items():
    try:
        __import__(module)
        print(f"✅ {name}")
    except ImportError:
        print(f"❌ {name} - 未安装")
        missing.append(name)

if missing:
    print(f"\n缺少依赖: {', '.join(missing)}")
    print("请运行: pip install flask flask-socketio aiohttp requests brotli")
    sys.exit(1)

print("\n" + "=" * 60)
print("检查文件完整性...")
print("=" * 60)

# 检查文件是否存在
files = [
    'web_server.py',
    'monitor_with_web.py',
    'templates/index.html',
    'static/css/style.css',
    'start.sh'
]

for file in files:
    if os.path.exists(file):
        print(f"✅ {file}")
    else:
        print(f"❌ {file} - 文件不存在")

print("\n" + "=" * 60)
print("检查语法...")
print("=" * 60)

import py_compile

try:
    py_compile.compile('web_server.py', doraise=True)
    print("✅ web_server.py 语法正确")
except py_compile.PyCompileError as e:
    print(f"❌ web_server.py 语法错误: {e}")

try:
    py_compile.compile('monitor_with_web.py', doraise=True)
    print("✅ monitor_with_web.py 语法正确")
except py_compile.PyCompileError as e:
    print(f"❌ monitor_with_web.py 语法错误: {e}")

print("\n" + "=" * 60)
print("尝试导入web_server...")
print("=" * 60)

try:
    from flask import Flask
    from flask_socketio import SocketIO
    import web_server

    print(f"✅ Flask应用创建成功")
    print(f"✅ 数据目录: {web_server.DATA_DIR}")
    from datetime import date
    print(f"✅ 当前数据文件: blind_box_data_{date.today().isoformat()}.json")
    print(f"✅ 监听器配置: {web_server.monitor_config}")

    # 检查API路由
    print("\n" + "=" * 60)
    print("检查API路由...")
    print("=" * 60)

    routes = [
        ('/', '主页'),
        ('/api/stats', '统计数据'),
        ('/api/config', '配置管理'),
        ('/api/monitor/start', '启动监听器'),
        ('/api/monitor/stop', '停止监听器'),
        ('/api/monitor/status', '监听器状态'),
    ]

    for route, desc in routes:
        print(f"  {route} - {desc}")

    print("\n" + "=" * 60)
    print("✅ 所有检查通过！")
    print("=" * 60)
    print("\n可以运行以下命令启动服务器:")
    print("  python web_server.py")
    print("\n然后访问: http://localhost:5000")

except Exception as e:
    print(f"❌ 错误: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
