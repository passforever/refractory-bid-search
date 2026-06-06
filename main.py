"""
耐火材料招标采购信息搜索工具 - 主程序
一键运行，自动搜索、过滤、生成报告
支持 PyInstaller 打包为 EXE
"""

import os
import sys
import webbrowser
import logging
from datetime import datetime

# 修复 Windows 终端 UTF-8 编码
if sys.platform == "win32":
    os.system("")  # 启用 ANSI 转义
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# ===== 路径解析：兼容 PyInstaller 打包和源码运行 =====
def get_app_dir():
    """获取应用程序所在目录（兼容 PyInstaller 打包）"""
    if getattr(sys, 'frozen', False):
        # PyInstaller 打包后的 exe 所在目录
        return os.path.dirname(sys.executable)
    else:
        # 源码运行时的脚本目录
        return os.path.dirname(os.path.abspath(__file__))

APP_DIR = get_app_dir()

# 添加路径
sys.path.insert(0, APP_DIR)

# 确保 reports 目录存在于 exe 旁边
REPORTS_DIR = os.path.join(APP_DIR, "reports")
os.makedirs(REPORTS_DIR, exist_ok=True)

import config
from search_engine import SearchScheduler
from report_generator import generate_html_report

logger = logging.getLogger(__name__)


def main():
    print("=" * 70)
    print("  [耐火材料招标采购信息搜索工具]")
    print("  " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    print("=" * 70)
    print()

    # 初始化搜索调度器
    scheduler = SearchScheduler()

    # 选择搜索模式
    print("请选择搜索模式：")
    print("  1. 快速搜索（仅搜索招标/采购关键词，约3分钟）")
    print("  2. 标准搜索（搜索招标+窑炉维修关键词，约8分钟）")
    print("  3. 完整搜索（搜索所有关键词，约15分钟）")
    print("  4. 自定义关键词搜索")
    print()

    try:
        choice = input("请输入选项 (1-4，默认2): ").strip() or "2"
    except (EOFError, KeyboardInterrupt):
        choice = "2"
        print("2")

    keywords = []
    if choice == "1":
        keywords = config.BID_KEYWORDS
        print(f"\n>> 快速搜索模式：共 {len(keywords)} 个关键词")
    elif choice == "2":
        keywords = config.BID_KEYWORDS + config.FURNACE_KEYWORDS
        print(f"\n>> 标准搜索模式：共 {len(keywords)} 个关键词")
    elif choice == "3":
        keywords = config.ALL_KEYWORDS
        print(f"\n>> 完整搜索模式：共 {len(keywords)} 个关键词")
    elif choice == "4":
        print("\n请输入自定义关键词（每行一个，空行结束）：")
        while True:
            try:
                kw = input("  > ").strip()
                if not kw:
                    break
                keywords.append(kw)
            except (EOFError, KeyboardInterrupt):
                break
        if not keywords:
            print("未输入关键词，使用标准搜索模式")
            keywords = config.BID_KEYWORDS + config.FURNACE_KEYWORDS
        else:
            print(f"\n>> 自定义搜索模式：共 {len(keywords)} 个关键词")
    else:
        print("无效选项，使用标准搜索模式")
        keywords = config.BID_KEYWORDS + config.FURNACE_KEYWORDS

    # 执行搜索
    est_min = len(keywords) * 2 // 60 + 1
    est_max = len(keywords) * 4 // 60 + 1
    print(f"\n{'-' * 70}")
    print(f"  开始搜索... 预计耗时 {est_min}-{est_max} 分钟")
    print(f"{'-' * 70}\n")

    report = scheduler.run_search(keywords)

    # 生成报告
    print(f"\n{'-' * 70}")
    print("  正在生成报告...")
    print(f"{'-' * 70}")

    filepath = generate_html_report(report)

    print(f"\n[OK] 报告已生成: {filepath}")
    print(f"  总结果数: {report.total_results}")
    print(f"  招标采购: {report.category_stats.get('招标采购', 0)} 条")
    print(f"  材料采购: {report.category_stats.get('材料采购', 0)} 条")
    print(f"  窑炉维修: {report.category_stats.get('窑炉维修', 0)} 条")

    if report.errors:
        print(f"\n[!] 搜索过程中有 {len(report.errors)} 个错误（部分结果可能不完整）")

    # 自动打开报告
    print("\n>> 正在打开报告...")
    webbrowser.open("file://" + filepath.replace("\\", "/"))

    print("\n" + "=" * 70)
    print("  [OK] 搜索完成！报告已在浏览器中打开")
    print("=" * 70)

    # 等待用户确认退出
    try:
        input("\n按 Enter 键退出...")
    except (EOFError, KeyboardInterrupt):
        pass


if __name__ == "__main__":
    main()
