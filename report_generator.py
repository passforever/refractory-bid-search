"""
耐火材料招标采购信息搜索工具 - HTML报告生成器
生成精美的可视化报告，支持分类查看、时间筛选
"""

import os
import sys
from datetime import datetime
from typing import List, Dict

import config
from search_engine import SearchResult, SearchReport


def _get_app_dir():
    """获取应用程序目录（兼容 PyInstaller 打包）"""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def generate_html_report(report: SearchReport) -> str:
    """生成HTML报告"""

    today = datetime.now().strftime(config.DATE_FORMAT)
    output_dir = os.path.join(_get_app_dir(), config.REPORT_DIR)
    os.makedirs(output_dir, exist_ok=True)

    filename = config.REPORT_FILENAME_FORMAT.format(date=today)
    filepath = os.path.join(output_dir, filename)

    # 分类结果
    bid_results = [r for r in report.results if r.category == "招标采购"]
    material_results = [r for r in report.results if r.category == "材料采购"]
    furnace_results = [r for r in report.results if r.category == "窑炉维修"]

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>耐火材料招标采购信息日报 - {today}</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
            background: linear-gradient(135deg, #0c0c1d 0%, #1a1a2e 50%, #16213e 100%);
            color: #e0e0e0;
            min-height: 100vh;
            line-height: 1.6;
        }}

        .container {{
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
        }}

        /* ===== Header ===== */
        .header {{
            text-align: center;
            padding: 40px 20px;
            margin-bottom: 30px;
            background: rgba(255,255,255,0.03);
            border-radius: 16px;
            border: 1px solid rgba(255,255,255,0.06);
            backdrop-filter: blur(20px);
        }}

        .header h1 {{
            font-size: 2rem;
            background: linear-gradient(135deg, #f97316, #ef4444, #ec4899);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            margin-bottom: 8px;
            font-weight: 800;
            letter-spacing: 2px;
        }}

        .header .subtitle {{
            color: #94a3b8;
            font-size: 0.95rem;
        }}

        .header .date-badge {{
            display: inline-block;
            margin-top: 12px;
            padding: 6px 20px;
            background: linear-gradient(135deg, rgba(249,115,22,0.2), rgba(239,68,68,0.2));
            border: 1px solid rgba(249,115,22,0.3);
            border-radius: 20px;
            color: #fb923c;
            font-weight: 600;
            font-size: 0.9rem;
        }}

        /* ===== Stats Cards ===== */
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 16px;
            margin-bottom: 30px;
        }}

        .stat-card {{
            background: rgba(255,255,255,0.04);
            border: 1px solid rgba(255,255,255,0.08);
            border-radius: 14px;
            padding: 24px 20px;
            text-align: center;
            transition: transform 0.3s ease, box-shadow 0.3s ease;
        }}

        .stat-card:hover {{
            transform: translateY(-4px);
            box-shadow: 0 12px 40px rgba(0,0,0,0.3);
        }}

        .stat-card .number {{
            font-size: 2.4rem;
            font-weight: 800;
            margin-bottom: 4px;
        }}

        .stat-card .label {{
            color: #94a3b8;
            font-size: 0.85rem;
            text-transform: uppercase;
            letter-spacing: 1px;
        }}

        .stat-card.total .number {{ background: linear-gradient(135deg, #60a5fa, #3b82f6); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; }}
        .stat-card.bid .number {{ background: linear-gradient(135deg, #f97316, #ea580c); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; }}
        .stat-card.material .number {{ background: linear-gradient(135deg, #10b981, #059669); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; }}
        .stat-card.furnace .number {{ background: linear-gradient(135deg, #ec4899, #db2777); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; }}

        .stat-card.total {{ border-color: rgba(96,165,250,0.2); }}
        .stat-card.bid {{ border-color: rgba(249,115,22,0.2); }}
        .stat-card.material {{ border-color: rgba(16,185,129,0.2); }}
        .stat-card.furnace {{ border-color: rgba(236,72,153,0.2); }}

        /* ===== Tab Navigation ===== */
        .tab-nav {{
            display: flex;
            gap: 8px;
            margin-bottom: 20px;
            flex-wrap: wrap;
        }}

        .tab-btn {{
            padding: 10px 24px;
            border: 1px solid rgba(255,255,255,0.1);
            border-radius: 10px;
            background: rgba(255,255,255,0.03);
            color: #94a3b8;
            cursor: pointer;
            font-size: 0.9rem;
            font-weight: 600;
            transition: all 0.3s ease;
        }}

        .tab-btn:hover {{
            background: rgba(255,255,255,0.08);
            color: #e2e8f0;
        }}

        .tab-btn.active {{
            background: linear-gradient(135deg, rgba(249,115,22,0.25), rgba(239,68,68,0.2));
            border-color: rgba(249,115,22,0.4);
            color: #fb923c;
        }}

        .tab-btn .count {{
            display: inline-block;
            margin-left: 6px;
            background: rgba(255,255,255,0.1);
            padding: 1px 8px;
            border-radius: 8px;
            font-size: 0.75rem;
        }}

        .tab-btn.active .count {{
            background: rgba(249,115,22,0.3);
        }}

        /* ===== Result Cards ===== */
        .results-section {{
            display: none;
        }}

        .results-section.active {{
            display: block;
        }}

        .result-card {{
            background: rgba(255,255,255,0.04);
            border: 1px solid rgba(255,255,255,0.07);
            border-radius: 14px;
            padding: 20px 24px;
            margin-bottom: 14px;
            transition: all 0.3s ease;
            position: relative;
            overflow: hidden;
        }}

        .result-card::before {{
            content: '';
            position: absolute;
            left: 0;
            top: 0;
            bottom: 0;
            width: 4px;
            border-radius: 4px 0 0 4px;
        }}

        .result-card.bid-card::before {{ background: linear-gradient(180deg, #f97316, #ea580c); }}
        .result-card.material-card::before {{ background: linear-gradient(180deg, #10b981, #059669); }}
        .result-card.furnace-card::before {{ background: linear-gradient(180deg, #ec4899, #db2777); }}

        .result-card:hover {{
            background: rgba(255,255,255,0.07);
            border-color: rgba(255,255,255,0.12);
            transform: translateX(4px);
        }}

        .result-card .card-header {{
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 8px;
            gap: 12px;
        }}

        .result-card .title {{
            font-size: 1.05rem;
            font-weight: 700;
            color: #f1f5f9;
            flex: 1;
        }}

        .result-card .title a {{
            color: inherit;
            text-decoration: none;
            transition: color 0.2s;
        }}

        .result-card .title a:hover {{
            color: #fb923c;
        }}

        .result-card .score-badge {{
            flex-shrink: 0;
            padding: 3px 10px;
            border-radius: 8px;
            font-size: 0.75rem;
            font-weight: 700;
        }}

        .score-high {{ background: rgba(16,185,129,0.2); color: #34d399; border: 1px solid rgba(16,185,129,0.3); }}
        .score-mid {{ background: rgba(249,115,22,0.2); color: #fb923c; border: 1px solid rgba(249,115,22,0.3); }}
        .score-low {{ background: rgba(148,163,184,0.15); color: #94a3b8; border: 1px solid rgba(148,163,184,0.2); }}

        .result-card .snippet {{
            color: #94a3b8;
            font-size: 0.88rem;
            margin-bottom: 10px;
            line-height: 1.5;
            display: -webkit-box;
            -webkit-line-clamp: 3;
            -webkit-box-orient: vertical;
            overflow: hidden;
        }}

        .result-card .meta {{
            display: flex;
            gap: 16px;
            flex-wrap: wrap;
            font-size: 0.78rem;
            color: #64748b;
        }}

        .result-card .meta span {{
            display: flex;
            align-items: center;
            gap: 4px;
        }}

        .result-card .meta .category-tag {{
            padding: 2px 8px;
            border-radius: 6px;
            font-weight: 600;
        }}

        .tag-bid {{ background: rgba(249,115,22,0.15); color: #fb923c; }}
        .tag-material {{ background: rgba(16,185,129,0.15); color: #34d399; }}
        .tag-furnace {{ background: rgba(236,72,153,0.15); color: #f472b6; }}

        /* ===== Empty State ===== */
        .empty-state {{
            text-align: center;
            padding: 60px 20px;
            color: #475569;
        }}

        .empty-state .icon {{
            font-size: 3rem;
            margin-bottom: 12px;
        }}

        /* ===== Errors ===== */
        .errors-section {{
            margin-top: 30px;
            padding: 20px;
            background: rgba(239,68,68,0.08);
            border: 1px solid rgba(239,68,68,0.2);
            border-radius: 14px;
        }}

        .errors-section h3 {{
            color: #f87171;
            margin-bottom: 10px;
            font-size: 0.95rem;
        }}

        .errors-section ul {{
            list-style: none;
            color: #fca5a5;
            font-size: 0.82rem;
        }}

        .errors-section li {{
            padding: 4px 0;
        }}

        /* ===== Footer ===== */
        .footer {{
            text-align: center;
            padding: 30px;
            color: #334155;
            font-size: 0.8rem;
            margin-top: 40px;
            border-top: 1px solid rgba(255,255,255,0.05);
        }}

        /* ===== Responsive ===== */
        @media (max-width: 768px) {{
            .container {{ padding: 12px; }}
            .header h1 {{ font-size: 1.5rem; }}
            .stats-grid {{ grid-template-columns: repeat(2, 1fr); gap: 10px; }}
            .stat-card {{ padding: 16px 12px; }}
            .stat-card .number {{ font-size: 1.8rem; }}
            .result-card {{ padding: 14px 16px; }}
            .tab-btn {{ padding: 8px 16px; font-size: 0.82rem; }}
        }}

        /* ===== Scrollbar ===== */
        ::-webkit-scrollbar {{ width: 8px; }}
        ::-webkit-scrollbar-track {{ background: rgba(0,0,0,0.2); }}
        ::-webkit-scrollbar-thumb {{ background: rgba(255,255,255,0.1); border-radius: 4px; }}
        ::-webkit-scrollbar-thumb:hover {{ background: rgba(255,255,255,0.2); }}

        /* ===== Highlight keyword ===== */
        .highlight {{
            background: rgba(249,115,22,0.3);
            color: #fb923c;
            padding: 0 2px;
            border-radius: 3px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <!-- Header -->
        <div class="header">
            <h1>🔥 耐火材料招标采购信息日报</h1>
            <p class="subtitle">自动全网搜索 | 多源聚合 | 智能分类</p>
            <div class="date-badge">📅 {today} | 搜索时间: {report.search_time}</div>
        </div>

        <!-- Stats -->
        <div class="stats-grid">
            <div class="stat-card total">
                <div class="number">{report.total_results}</div>
                <div class="label">总结果数</div>
            </div>
            <div class="stat-card bid">
                <div class="number">{len(bid_results)}</div>
                <div class="label">招标采购</div>
            </div>
            <div class="stat-card material">
                <div class="number">{len(material_results)}</div>
                <div class="label">材料采购</div>
            </div>
            <div class="stat-card furnace">
                <div class="number">{len(furnace_results)}</div>
                <div class="label">窑炉维修</div>
            </div>
        </div>

        <!-- Tab Navigation -->
        <div class="tab-nav">
            <button class="tab-btn active" onclick="switchTab('all')">
                全部 <span class="count">{report.total_results}</span>
            </button>
            <button class="tab-btn" onclick="switchTab('bid')">
                🏛️ 招标采购 <span class="count">{len(bid_results)}</span>
            </button>
            <button class="tab-btn" onclick="switchTab('material')">
                🧱 材料采购 <span class="count">{len(material_results)}</span>
            </button>
            <button class="tab-btn" onclick="switchTab('furnace')">
                🏭 窑炉维修 <span class="count">{len(furnace_results)}</span>
            </button>
        </div>

        <!-- All Results -->
        <div class="results-section active" id="tab-all">
            {_render_results(report.results, "all")}
        </div>

        <!-- Bid Results -->
        <div class="results-section" id="tab-bid">
            {_render_results(bid_results, "bid")}
        </div>

        <!-- Material Results -->
        <div class="results-section" id="tab-material">
            {_render_results(material_results, "material")}
        </div>

        <!-- Furnace Results -->
        <div class="results-section" id="tab-furnace">
            {_render_results(furnace_results, "furnace")}
        </div>

        <!-- Errors -->
        {"".join(_render_errors(report.errors)) if report.errors else ""}

        <!-- Footer -->
        <div class="footer">
            <p>耐火材料招标采购信息搜索工具 | 每日自动搜索 | 数据仅供参考</p>
            <p style="margin-top:4px;">搜索关键词: {report.total_keywords} 个 | 搜索引擎: {len(report.source_stats)} 个</p>
        </div>
    </div>

    <script>
        function switchTab(tabName) {{
            // 隐藏所有内容
            document.querySelectorAll('.results-section').forEach(s => s.classList.remove('active'));
            // 取消所有按钮选中
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));

            // 显示目标内容
            document.getElementById('tab-' + tabName).classList.add('active');
            // 选中对应按钮
            event.currentTarget.classList.add('active');
        }}

        // 为结果卡片添加入场动画
        document.addEventListener('DOMContentLoaded', function() {{
            const cards = document.querySelectorAll('.result-card');
            cards.forEach((card, index) => {{
                card.style.opacity = '0';
                card.style.transform = 'translateY(20px)';
                setTimeout(() => {{
                    card.style.transition = 'opacity 0.4s ease, transform 0.4s ease';
                    card.style.opacity = '1';
                    card.style.transform = 'translateY(0)';
                }}, index * 60);
            }});
        }});
    </script>
</body>
</html>"""

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(html)

    return filepath


def _render_results(results: List[SearchResult], category: str) -> str:
    """渲染结果列表"""
    if not results:
        return """
        <div class="empty-state">
            <div class="icon">📭</div>
            <p>暂无此类结果</p>
        </div>"""

    cards = []
    for r in results:
        card_class = f"{category}-card" if category != "all" else f"{_get_card_class(r.category)}-card"
        tag_class = f"tag-{_get_tag_class(r.category)}"
        score_class = _get_score_class(r.relevance_score)

        # 截断过长的 URL 用于显示
        display_url = r.url[:80] + "..." if len(r.url) > 80 else r.url

        card = f"""
        <div class="result-card {card_class}">
            <div class="card-header">
                <div class="title">
                    <a href="{_escape_html(r.url)}" target="_blank" rel="noopener">
                        {_escape_html(r.title)}
                    </a>
                </div>
                <span class="score-badge {score_class}">{r.relevance_score:.0f}分</span>
            </div>
            <div class="snippet">{_escape_html(r.snippet)}</div>
            <div class="meta">
                <span class="category-tag {tag_class}">{r.category}</span>
                <span>📍 {_escape_html(r.source)}</span>
                <span>🔑 {_escape_html(r.keyword)}</span>
                {f'<span>📅 {_escape_html(r.date)}</span>' if r.date else ''}
                <span>🔗 {_escape_html(display_url)}</span>
            </div>
        </div>"""
        cards.append(card)

    return "".join(cards)


def _render_errors(errors: List[str]) -> List[str]:
    """渲染错误信息"""
    if not errors:
        return []

    items = [f"<li>{_escape_html(e)}</li>" for e in errors]
    return [f"""
    <div class="errors-section">
        <h3>⚠️ 搜索过程中的错误 ({len(errors)})</h3>
        <ul>{"".join(items)}</ul>
    </div>"""]


def _get_card_class(category: str) -> str:
    return {"招标采购": "bid", "材料采购": "material", "窑炉维修": "furnace"}.get(category, "bid")


def _get_tag_class(category: str) -> str:
    return _get_card_class(category)


def _get_score_class(score: float) -> str:
    if score >= 70:
        return "score-high"
    elif score >= 40:
        return "score-mid"
    return "score-low"


def _escape_html(text: str) -> str:
    """转义HTML特殊字符"""
    if not text:
        return ""
    return (text
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&#x27;"))
