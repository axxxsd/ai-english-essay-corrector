@echo off
chcp 65001 >nul
echo ============================================
echo   ✍️  智能英语作文批改系统
echo ============================================
echo.

REM 检查 Python 是否可用
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ 未检测到 Python，请先安装 Python 3.8+
    echo    下载地址: https://www.python.org/downloads/
    pause
    exit /b 1
)

echo 🧪 正在运行冒烟测试...
python smoke_test.py
echo.

echo 🚀 启动主程序...
python desktop_app.py

pause
