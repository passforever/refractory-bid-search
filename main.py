"""
耐火材料招标采购信息搜索工具 - 主程序
一键运行，自动搜索、过滤、生成报告
支持关键词管理、API数据源配置
支持 PyInstaller 打包为 EXE
"""

import os
import sys
import webbrowser
import logging
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

REPORTS_DIR = os.path.join(APP_DIR, "reports")
os.makedirs(REPORTS_DIR, exist_ok=True)

import config
from config import ConfigManager
from search_engine import SearchScheduler
from report_generator import generate_html_report

logger = logging.getLogger(__name__)


def main():
    print("=" * 70)
    print("  耐火材料招标采购信息搜索工具 v2.0")
    print("  " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    print("=" * 70)
    print()

    while True:
        print("请选择功能：")
        print("  1. 🚀 快速搜索（招标/采购关键词，约3分钟）")
        print("  2. 🔍 标准搜索（招标+窑炉维修，约8分钟）")
        print("  3. 📋 完整搜索（所有关键词，约15分钟）")
        print("  4. ✏️  自定义关键词搜索")
        print("  5. ⚙️  关键词管理（增删改查）")
        print("  6. 🔗 API数据源管理（配置固定网站API）")
        print("  0. 退出")
        print()

        try:
            choice = input("请输入选项 (0-6，默认2): ").strip() or "2"
        except (EOFError, KeyboardInterrupt):
            print()
            return

        if choice == "0":
            print("再见！")
            return
        elif choice in ("1", "2", "3", "4"):
            run_search(choice)
            break
        elif choice == "5":
            manage_keywords()
        elif choice == "6":
            manage_api_sources()
        else:
            print("无效选项，请重新选择\n")


def run_search(choice: str):
    keywords = []
    if choice == "1":
        keywords = config.BID_KEYWORDS
        print(f"\n>> 快速搜索模式：共 {len(keywords)} 个关键词")
    elif choice == "2":
        keywords = config.BID_KEYWORDS + config.FURNACE_KEYWORDS
        print(f"\n>> 标准搜索模式：共 {len(keywords)} 个关键词")
    elif choice == "3":
        keywords = ConfigManager.get_keywords()
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

    est_min = len(keywords) * 2 // 60 + 1
    est_max = len(keywords) * 4 // 60 + 1
    print(f"\n{'-' * 70}")
    print(f"  开始搜索... 预计耗时 {est_min}-{est_max} 分钟")
    print(f"{'-' * 70}\n")

    scheduler = SearchScheduler()
    report = scheduler.run_search(keywords)

    print(f"\n{'-' * 70}")
    print("  正在生成报告...")
    print(f"{'-' * 70}")

    filepath = generate_html_report(report)

    print(f"\n✅ 报告已生成: {filepath}")
    print(f"  总结果数: {report.total_results}")
    print(f"  招标采购: {report.category_stats.get('招标采购', 0)} 条")
    print(f"  材料采购: {report.category_stats.get('材料采购', 0)} 条")
    print(f"  窑炉维修: {report.category_stats.get('窑炉维修', 0)} 条")

    if report.errors:
        print(f"\n⚠️ 搜索过程中有 {len(report.errors)} 个错误")

    print("\n>> 正在打开报告...")
    webbrowser.open("file://" + filepath.replace("\\", "/"))

    print("\n" + "=" * 70)
    print("  ✅ 搜索完成！报告已在浏览器中打开")
    print("=" * 70)

    try:
        input("\n按 Enter 键退出...")
    except (EOFError, KeyboardInterrupt):
        pass


def manage_keywords():
    while True:
        current = ConfigManager.get_keywords()
        print("\n" + "=" * 70)
        print("  ⚙️ 关键词管理")
        print("=" * 70)
        print(f"\n当前关键词列表（共 {len(current)} 个）：")
        print("-" * 50)

        bid_kws = [k for k in current if any(w in k for w in ["招标", "采购", "竞标", "比价", "谈判"]) and not any(w in k for w in ["高铝砖","粘土砖","轻质砖","硅砖","浇注料","不定型","泥浆","散料","喷涂料","可塑料"])]
        furnace_kws = [k for k in current if any(w in k for w in ["高炉", "热风炉", "焦炉", "窑炉", "加热炉", "回转窑", "锅炉"])]
        material_kws = [k for k in current if any(w in k for w in ["高铝砖", "粘土砖", "轻质砖", "硅砖", "浇注料", "不定型", "泥浆", "散料", "喷涂料", "可塑料"])]

        if bid_kws:
            print("\n  🏛️ 招标采购类:")
            for i, kw in enumerate(bid_kws, 1):
                print(f"    {i}. {kw}")
        if furnace_kws:
            print("\n  🏭 窑炉维修类:")
            for i, kw in enumerate(furnace_kws, 1):
                print(f"    {i}. {kw}")
        if material_kws:
            print("\n  🧱 材料采购类:")
            for i, kw in enumerate(material_kws, 1):
                print(f"    {i}. {kw}")

        print("\n操作：")
        print("  1. 添加关键词")
        print("  2. 删除关键词")
        print("  3. 重置为默认关键词")
        print("  0. 返回主菜单")
        print()

        try:
            op = input("请选择操作 (0-3): ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return

        if op == "0":
            return
        elif op == "1":
            print("\n请输入要添加的关键词（每行一个，空行结束）：")
            new_kws = []
            while True:
                try:
                    kw = input("  + ").strip()
                    if not kw:
                        break
                    new_kws.append(kw)
                except (EOFError, KeyboardInterrupt):
                    break
            if new_kws:
                current.extend(new_kws)
                ConfigManager.set_keywords(current)
                print(f"✅ 已添加 {len(new_kws)} 个关键词")
            else:
                print("未输入任何关键词")
        elif op == "2":
            print("\n请输入要删除的关键词编号（从上面列表中选，多个用逗号分隔）：")
            try:
                nums = input("  编号: ").strip()
                all_listed = bid_kws + furnace_kws + material_kws
                indices = [int(n.strip()) - 1 for n in nums.split(",") if n.strip().isdigit()]
                to_remove = set()
                for idx in indices:
                    if 0 <= idx < len(all_listed):
                        to_remove.add(all_listed[idx])
                if to_remove:
                    current = [kw for kw in current if kw not in to_remove]
                    ConfigManager.set_keywords(current)
                    print(f"✅ 已删除 {len(to_remove)} 个关键词")
                else:
                    print("无效编号")
            except (ValueError, EOFError, KeyboardInterrupt):
                print("输入无效")
        elif op == "3":
            ConfigManager.set_keywords(config.ALL_KEYWORDS)
            print("✅ 已重置为默认关键词")
        else:
            print("无效选项")


def manage_api_sources():
    while True:
        sources = ConfigManager.get_api_sources()
        print("\n" + "=" * 70)
        print("  🔗 API数据源管理")
        print("=" * 70)
        print(f"\n当前API数据源（共 {len(sources)} 个）：")
        print("-" * 50)

        for i, (key, src) in enumerate(sources.items(), 1):
            status = "✅ 已启用" if src.get("enabled", False) else "❌ 未启用"
            print(f"  {i}. [{status}] {src.get('name', key)}")
            print(f"     URL: {src.get('api_url', '未配置')}")
            print(f"     类型: {src.get('api_type', 'html')}")

        print("\n操作：")
        print("  1. 添加API数据源")
        print("  2. 启用/禁用数据源")
        print("  3. 删除数据源")
        print("  0. 返回主菜单")
        print()

        try:
            op = input("请选择操作 (0-3): ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return

        if op == "0":
            return
        elif op == "1":
            print("\n--- 添加API数据源 ---")
            try:
                key = input("  数据源标识（英文，如 myapi）: ").strip()
                name = input("  数据源名称（如：XX招标网）: ").strip()
                api_url = input("  API URL（如：https://example.com/search）: ").strip()
                api_type = input("  API类型（html/json/rss，默认html）: ").strip() or "html"

                print("\n  CSS选择器配置（HTML类型需要）：")
                container = input("    结果容器选择器（如 div.result-item）: ").strip() or "div"
                title_sel = input("    标题选择器（如 h3 a）: ").strip() or "a"
                url_sel = input("    链接选择器（如 h3 a[href]）: ").strip() or "a[href]"
                snippet_sel = input("    摘要选择器（如 p.desc）: ").strip() or "p"
                date_sel = input("    日期选择器（如 span.date）: ").strip() or "span"

                print("\n  请求参数模板（可选，格式：key=value，每行一个，空行结束）：")
                print("  可用变量：{keyword} {today} {date_30d_ago}")
                params = {}
                while True:
                    try:
                        line = input("    ").strip()
                        if not line:
                            break
                        if "=" in line:
                            k, v = line.split("=", 1)
                            params[k.strip()] = v.strip()
                    except (EOFError, KeyboardInterrupt):
                        break

                src_config = {
                    "name": name,
                    "enabled": True,
                    "api_url": api_url,
                    "api_type": api_type,
                    "params": params,
                    "encoding": "utf-8",
                    "result_selector": {
                        "container": container,
                        "title": title_sel,
                        "url": url_sel,
                        "snippet": snippet_sel,
                        "date": date_sel,
                    }
                }

                ConfigManager.add_api_source(key, src_config)
                print(f"\n✅ 已添加数据源: {name}")
            except (EOFError, KeyboardInterrupt):
                print("\n操作取消")

        elif op == "2":
            print("\n请输入要切换状态的数据源编号：")
            try:
                num = int(input("  编号: ").strip()) - 1
                keys = list(sources.keys())
                if 0 <= num < len(keys):
                    key = keys[num]
                    current_status = sources[key].get("enabled", False)
                    new_status = not current_status
                    ConfigManager.toggle_api_source(key, new_status)
                    status_text = "启用" if new_status else "禁用"
                    print(f"✅ 已{status_text}: {sources[key].get('name', key)}")
                else:
                    print("无效编号")
            except (ValueError, EOFError, KeyboardInterrupt):
                print("输入无效")

        elif op == "3":
            print("\n请输入要删除的数据源编号：")
            try:
                num = int(input("  编号: ").strip()) - 1
                keys = list(sources.keys())
                if 0 <= num < len(keys):
                    key = keys[num]
                    name = sources[key].get('name', key)
                    ConfigManager.remove_api_source(key)
                    print(f"✅ 已删除: {name}")
                else:
                    print("无效编号")
            except (ValueError, EOFError, KeyboardInterrupt):
                print("输入无效")


if __name__ == "__main__":
    main()
