"""
快速测试脚本 - 仅搜索少量关键词验证功能
"""

import os
import sys
import webbrowser

# 修复 Windows 终端 UTF-8 编码
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
from search_engine import SearchScheduler
from report_generator import generate_html_report


def quick_test():
    print("🧪 快速测试模式 - 仅搜索2个关键词验证功能\n")

    # 使用少量关键词测试
    test_keywords = [
        "耐火材料 招标",
        "高铝砖 采购",
    ]

    scheduler = SearchScheduler()
    report = scheduler.run_search(test_keywords)

    filepath = generate_html_report(report)

    print(f"\n✅ 测试完成！")
    print(f"   报告路径: {filepath}")
    print(f"   总结果数: {report.total_results}")
    print(f"   分类统计: {report.category_stats}")

    # 打开报告
    webbrowser.open("file://" + filepath.replace("\\", "/"))

    return filepath


if __name__ == "__main__":
    quick_test()
