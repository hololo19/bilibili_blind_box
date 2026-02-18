@echo off
chcp 65001 >nul
echo ========================================
echo   B站盲盒统计工具 - 自动打包脚本
echo ========================================
echo.

echo [1/4] 检查Python环境...
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ 错误：未找到Python，请先安装Python 3.8+
    pause
    exit /b 1
)
echo ✅ Python环境正常
echo.

echo [2/4] 安装依赖库...
pip install -r requirements_gui.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
if errorlevel 1 (
    echo ❌ 错误：依赖安装失败
    pause
    exit /b 1
)
echo ✅ 依赖安装完成
echo.

echo [3/4] 开始打包（这可能需要几分钟）...
pyinstaller --clean build_exe.spec
if errorlevel 1 (
    echo ❌ 错误：打包失败
    pause
    exit /b 1
)
echo ✅ 打包完成
echo.

echo [4/4] 复制到发布目录...
if not exist "发布文件" mkdir "发布文件"
xcopy /E /I /Y "dist\盲盒统计工具.exe" "发布文件\"
echo ✅ 文件已复制到 发布文件 文件夹
echo.

echo ========================================
echo   打包成功！
echo ========================================
echo.
echo 📦 可执行文件位置：发布文件\盲盒统计工具.exe
echo.
echo 📝 使用说明：
echo    1. 将 盲盒统计工具.exe 发送给使用者
echo    2. 双击运行即可，无需安装Python
echo    3. 首次运行可能需要几秒钟加载
echo.
echo ========================================
pause
