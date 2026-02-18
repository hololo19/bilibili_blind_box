@echo off
chcp 65001 >nul
echo ========================================
echo   正在打包成单个exe文件...
echo ========================================
echo.

echo [1/3] 安装依赖库...
pip install -r requirements_gui.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
if errorlevel 1 (
    echo.
    echo ❌ 依赖安装失败，请检查网络连接
    pause
    exit /b 1
)
echo ✅ 依赖安装完成
echo.

echo [2/3] 开始PyInstaller打包...
echo 这可能需要3-5分钟，请耐心等待...
pyinstaller --onefile --windowed --name="盲盒统计工具" --clean blind_box_gui.py
if errorlevel 1 (
    echo.
    echo ❌ 打包失败，请查看上方错误信息
    pause
    exit /b 1
)
echo ✅ 打包完成
echo.

echo [3/3] 验证生成的文件...
if exist "dist\盲盒统计工具.exe" (
    echo ✅ 文件生成成功
    dir "dist\盲盒统计工具.exe"
) else (
    echo ❌ 未找到生成的exe文件
)
echo.

echo ========================================
echo   🎉 打包完成！
echo ========================================
echo.
echo 📦 文件位置：dist\盲盒统计工具.exe
echo.
echo 下一步：
echo 1. 进入 dist 文件夹
echo 2. 双击测试 盲盒统计工具.exe 是否能正常运行
echo 3. 将exe文件和 使用说明.txt 一起发送给使用者
echo.
pause
