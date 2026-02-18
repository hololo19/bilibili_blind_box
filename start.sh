#!/bin/bash
# 启动脚本 - 只运行Web服务器
# 监听器通过Web界面启动

cd /app

echo "[启动] 盲盒统计Web服务器..."
echo "[提示] 监听器需要通过Web界面配置并手动启动"
echo ""

# 只启动Web服务器（前台运行）
python web_server.py
