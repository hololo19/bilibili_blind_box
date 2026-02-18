#!/bin/bash

echo "========================================"
echo "  盲盒统计Web服务 - Docker部署脚本"
echo "========================================"
echo ""

# 检查Docker是否安装
if ! command -v docker &> /dev/null; then
    echo "❌ 错误：未找到Docker，请先安装Docker"
    echo "   安装教程：https://docs.docker.com/get-docker/"
    exit 1
fi

echo "✅ Docker环境检测通过"
echo ""

# 创建数据目录
echo "[1/4] 创建数据目录..."
mkdir -p data
echo "✅ 数据目录已创建"
echo ""

# 构建镜像
echo "[2/4] 构建Docker镜像..."
docker build -t blind-box-stats:latest .
if [ $? -ne 0 ]; then
    echo "❌ 镜像构建失败"
    exit 1
fi
echo "✅ 镜像构建成功"
echo ""

# 启动容器
echo "[3/4] 启动容器..."
docker-compose up -d
if [ $? -ne 0 ]; then
    echo "❌ 容器启动失败"
    exit 1
fi
echo "✅ 容器启动成功"
echo ""

# 显示状态
echo "[4/4] 检查容器状态..."
docker-compose ps
echo ""

echo "========================================"
echo "  🎉 部署完成！"
echo "========================================"
echo ""
echo "📦 访问地址："
echo "   本地：http://localhost:5000"
echo "   公网：http://YOUR_IP:5000"
echo ""
echo "📁 数据目录：./data/"
echo "📋 日志查看：docker-compose logs -f"
echo "🛑 停止服务：docker-compose down"
echo "🔄 重启服务：docker-compose restart"
echo ""
echo "========================================"
