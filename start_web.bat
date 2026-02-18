@echo off
chcp 65001 >nul
echo ========================================
echo   快速测试Web服务器
echo ========================================
echo.

echo [步骤1] 检查Python环境
python --version
if errorlevel 1 (
    echo 错误：未找到Python
    echo 请确保在conda viper环境中运行
    pause
    exit /b 1
)
echo.

echo [步骤2] 检查依赖
echo 检查Flask...
python -c "from flask import Flask; print('Flask OK')" 2>nul
if errorlevel 1 (
    echo Flask未安装，请运行：pip install flask flask-socketio
    pause
    exit /b 1
)
echo Flask OK
echo.

echo [步骤3] 启动Web服务器
echo 正在启动服务器...
echo.
echo 访问地址：http://localhost:5000
echo 按Ctrl+C停止服务器
echo.
echo ========================================
pause

python web_server.py
