@echo off
chcp 65001 >nul 2>&1
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
title 耐火材料招标采购信息搜索工具

echo.
echo ================================================================
echo   耐火材料招标采购信息搜索工具
echo   双击运行即可，按提示操作
echo ================================================================
echo.

cd /d "%~dp0"

:: 检查 Python 是否安装
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未检测到 Python，请先安装 Python 3.8+
    echo    下载地址: https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
)

:: 检查并安装依赖
echo [信息] 检查依赖...
pip install -r requirements.txt -q 2>nul

:: 运行主程序
echo.
python main.py

pause
