"""
耐火材料招标采购信息搜索工具 v3.0 - 主程序
启动 Flask Web 服务器，支持前台展示 + 后台管理
支持 PyInstaller 打包为 EXE
"""

import os
import sys
import webbrowser
import logging
import threading
from datetime import datetime

# 修复 Windows 终端 UTF-8 编码
if sys.platform == "win32":
    os.system("")
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

def get_app_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

APP_DIR = get_app_dir()
sys.path.insert(0, APP_DIR)

import config
from app import start_server, init_db

logger = logging.getLogger(__name__)


def main():
    print("=" * 70)
    print("  耐火材料招标采购信息搜索工具 v3.0")
    print("  " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    print("=" * 70)
    print()
    print("  🌐 前台: http://127.0.0.1:8899")
    print("  📋 后台: http://127.0.0.1:8899/admin")
    print()
    print("  正在启动服务器...")
    print("  关闭此窗口即可停止服务")
    print("=" * 70)

    # 初始化数据库
    init_db()

    # 延迟打开浏览器
    def open_browser():
        import time
        time.sleep(2)
        webbrowser.open("http://127.0.0.1:8899")

    threading.Thread(target=open_browser, daemon=True).start()

    # 启动 Flask
    start_server()


if __name__ == "__main__":
    main()
