"""
耐火材料招标采购信息搜索工具 - HTML报告生成器 v3.0
苹果官网视觉风格 + 时效标注 + 链接有效性 + 更丰富信息展示
"""

import os
import sys
import urllib.parse
from datetime import datetime, timedelta
from typing import List, Dict

import config
from search_engine import SearchResult, SearchReport


def _get_app_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def _make_click_url(url: str, article_id: str = "") -> str:
    """生成可点击的URL：
    - 有效的http/https链接 → 直接使用
    - 百度重定向URL → 走Flask /go 代理
    - 非http的加密token → 走Flask /go 代理
    """
    if not url:
        return "#"

    # 已经是有效的http链接
    if url.startswith("http://") or url.startswith("https://"):
        # 百度重定向链接也走代理（确保能跟踪到真实URL并自动更新数据库）
        if "baidu.com/link" in url or "baidu.com/baidu.php" in url:
            return f"/go?url={urllib.parse.quote(url, safe='')}&id={article_id}"
        return url

    # 非http的加密token → 走代理（代理会尝试构造百度URL再跟踪重定向）
    return f"/go?url={urllib.parse.quote(url, safe='')}&id={article_id}"


def generate_html_report(report: SearchReport, return_html: bool = False, article_ids: Dict[str, str] = None) -> str:
    today = datetime.now().strftime(config.DATE_FORMAT)
    output_dir = os.path.join(_get_app_dir(), config.REPORT_DIR)
    os.makedirs(output_dir, exist_ok=True)

    filename = config.REPORT_FILENAME_FORMAT.format(date=today)
    filepath = os.path.join(output_dir, filename)

    # article_ids: url -> article_id 映射，用于Flask跳转代理
    if article_ids is None:
        article_ids = {}

    bid_results = [r for r in report.results if r.category == "招标采购"]
    material_results = [r for r in report.results if r.category == "材料采购"]
    furnace_results = [r for r in report.results if r.category == "窑炉维修"]

    # 时效信息
    cutoff_date = (datetime.now() - timedelta(days=config.MAX_DAYS_OLD)).strftime("%Y-%m-%d")
    expired_note = f"仅展示 {cutoff_date} 之后发布的资讯"

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>耐火材料招标采购信息日报 - {today}</title>
    <style>
        :root {{
            --bg: #fbfbfd;
            --card-bg: #ffffff;
            --text-primary: #1d1d1f;
            --text-secondary: #6e6e73;
            --text-tertiary: #86868b;
            --border: #d2d2d7;
            --border-light: #e8e8ed;
            --accent: #0071e3;
            --accent-hover: #0077ed;
            --green: #34c759;
            --orange: #ff9500;
            --pink: #ff2d55;
            --purple: #af52de;
            --radius: 18px;
            --radius-sm: 12px;
            --shadow-sm: 0 1px 3px rgba(0,0,0,0.04), 0 1px 2px rgba(0,0,0,0.06);
            --shadow-md: 0 4px 14px rgba(0,0,0,0.06), 0 2px 6px rgba(0,0,0,0.04);
            --shadow-lg: 0 8px 30px rgba(0,0,0,0.08), 0 4px 10px rgba(0,0,0,0.04);
            --font: -apple-system, BlinkMacSystemFont, "SF Pro Display", "SF Pro Text", "Helvetica Neue", "PingFang SC", "Microsoft YaHei", sans-serif;
        }}

        * {{ margin: 0; padding: 0; box-sizing: border-box; }}

        body {{
            font-family: var(--font);
            background: var(--bg);
            color: var(--text-primary);
            line-height: 1.5;
            -webkit-font-smoothing: antialiased;
        }}

        /* ===== Hero Section ===== */
        .hero {{
            text-align: center;
            padding: 80px 24px 60px;
            background: linear-gradient(180deg, #f5f5f7 0%, var(--bg) 100%);
        }}

        .hero-eyebrow {{
            font-size: 0.8rem;
            font-weight: 600;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            color: var(--text-tertiary);
            margin-bottom: 12px;
        }}

        .hero h1 {{
            font-size: clamp(2rem, 5vw, 3.2rem);
            font-weight: 700;
            letter-spacing: -0.02em;
            color: var(--text-primary);
            margin-bottom: 12px;
        }}

        .hero-date {{
            font-size: 1.1rem;
            color: var(--text-secondary);
            font-weight: 400;
        }}

        /* ===== Time Notice ===== */
        .time-notice {{
            text-align: center;
            padding: 10px 24px;
            background: rgba(0,113,227,0.04);
            color: var(--accent);
            font-size: 0.82rem;
            font-weight: 500;
        }}

        /* ===== Stats Bar ===== */
        .stats-bar {{
            display: flex;
            justify-content: center;
            gap: 48px;
            padding: 40px 24px;
            flex-wrap: wrap;
        }}

        .stat-item {{ text-align: center; }}

        .stat-number {{
            font-size: 2.8rem;
            font-weight: 700;
            letter-spacing: -0.03em;
            line-height: 1.1;
        }}

        .stat-number.blue {{ color: var(--accent); }}
        .stat-number.orange {{ color: var(--orange); }}
        .stat-number.green {{ color: var(--green); }}
        .stat-number.pink {{ color: var(--pink); }}

        .stat-label {{
            font-size: 0.82rem;
            font-weight: 500;
            color: var(--text-tertiary);
            margin-top: 4px;
            letter-spacing: 0.02em;
        }}

        /* ===== Tab Navigation ===== */
        .tab-container {{
            max-width: 980px;
            margin: 0 auto;
            padding: 0 24px;
        }}

        .tab-nav {{
            display: flex;
            gap: 6px;
            border-bottom: 1px solid var(--border-light);
            margin-bottom: 32px;
            overflow-x: auto;
            -webkit-overflow-scrolling: touch;
        }}

        .tab-btn {{
            padding: 12px 20px;
            border: none;
            background: none;
            color: var(--text-secondary);
            cursor: pointer;
            font-size: 0.92rem;
            font-weight: 500;
            font-family: var(--font);
            border-bottom: 2px solid transparent;
            transition: all 0.25s ease;
            white-space: nowrap;
        }}

        .tab-btn:hover {{ color: var(--text-primary); }}

        .tab-btn.active {{
            color: var(--accent);
            border-bottom-color: var(--accent);
        }}

        .tab-btn .count {{
            display: inline-block;
            margin-left: 4px;
            font-size: 0.78rem;
            color: var(--text-tertiary);
            font-weight: 400;
        }}

        .tab-btn.active .count {{ color: var(--accent); opacity: 0.7; }}

        /* ===== Results Section ===== */
        .results-section {{
            display: none;
            animation: fadeIn 0.4s ease;
        }}

        .results-section.active {{ display: block; }}

        @keyframes fadeIn {{
            from {{ opacity: 0; transform: translateY(8px); }}
            to {{ opacity: 1; transform: translateY(0); }}
        }}

        /* ===== Result Card ===== */
        .result-card {{
            background: var(--card-bg);
            border-radius: var(--radius);
            padding: 28px 32px;
            margin-bottom: 16px;
            box-shadow: var(--shadow-sm);
            border: 1px solid var(--border-light);
            transition: all 0.35s cubic-bezier(0.25, 0.46, 0.45, 0.94);
            position: relative;
        }}

        .result-card:hover {{
            box-shadow: var(--shadow-lg);
            transform: translateY(-2px);
            border-color: var(--border);
        }}

        .result-card::before {{
            content: '';
            position: absolute;
            left: 0;
            top: 20px;
            bottom: 20px;
            width: 3px;
            border-radius: 0 3px 3px 0;
        }}

        .result-card.cat-bid::before {{ background: var(--accent); }}
        .result-card.cat-material::before {{ background: var(--green); }}
        .result-card.cat-furnace::before {{ background: var(--pink); }}

        /* Invalid link indicator */
        .result-card.link-invalid {{
            opacity: 0.6;
            border-color: rgba(255,45,85,0.2);
        }}

        .result-card.link-invalid::after {{
            content: '链接不可访问';
            position: absolute;
            top: 12px;
            right: 16px;
            font-size: 0.72rem;
            color: var(--pink);
            background: rgba(255,45,85,0.06);
            padding: 2px 10px;
            border-radius: 10px;
        }}

        /* Card Title */
        .card-title {{
            font-size: 1.1rem;
            font-weight: 600;
            letter-spacing: -0.01em;
            line-height: 1.35;
            margin-bottom: 10px;
            padding-right: 100px;
        }}

        .card-title a {{
            color: var(--text-primary);
            text-decoration: none;
            transition: color 0.2s;
        }}

        .card-title a:hover {{ color: var(--accent); }}

        /* Card Snippet */
        .card-snippet {{
            color: var(--text-secondary);
            font-size: 0.9rem;
            line-height: 1.65;
            margin-bottom: 16px;
            display: -webkit-box;
            -webkit-line-clamp: 5;
            -webkit-box-orient: vertical;
            overflow: hidden;
        }}

        /* Extra Info Grid */
        .extra-info {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
            gap: 8px 20px;
            margin-bottom: 16px;
            padding: 14px 16px;
            background: #f5f5f7;
            border-radius: var(--radius-sm);
        }}

        .extra-item {{
            display: flex;
            align-items: center;
            gap: 6px;
            font-size: 0.82rem;
        }}

        .extra-item .label {{
            color: var(--text-tertiary);
            font-weight: 500;
            white-space: nowrap;
        }}

        .extra-item .value {{
            color: var(--text-primary);
            font-weight: 500;
        }}

        .extra-item .value.budget {{ color: var(--orange); font-weight: 600; }}
        .extra-item .value.deadline {{ color: var(--pink); font-weight: 600; }}

        /* Meta Tags */
        .card-meta {{
            display: flex;
            gap: 8px;
            flex-wrap: wrap;
            align-items: center;
        }}

        .tag {{
            display: inline-flex;
            align-items: center;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 0.75rem;
            font-weight: 500;
        }}

        .tag-bid {{ background: rgba(0,113,227,0.08); color: var(--accent); }}
        .tag-material {{ background: rgba(52,199,89,0.08); color: var(--green); }}
        .tag-furnace {{ background: rgba(255,45,85,0.08); color: var(--pink); }}

        .tag-score {{
            background: #f5f5f7;
            color: var(--text-secondary);
        }}

        .tag-score.high {{ background: rgba(52,199,89,0.1); color: var(--green); }}
        .tag-score.mid {{ background: rgba(255,149,0,0.1); color: var(--orange); }}

        .tag-source {{ background: #f5f5f7; color: var(--text-tertiary); }}
        .tag-date {{ background: none; color: var(--text-tertiary); padding: 4px 0; }}
        .tag-keyword {{ background: rgba(175,82,222,0.08); color: var(--purple); }}
        .tag-fresh {{ background: rgba(52,199,89,0.1); color: var(--green); }}
        .tag-contact {{ background: rgba(0,113,227,0.06); color: var(--accent); }}

        /* Visit Button */
        .visit-btn {{
            display: inline-flex;
            align-items: center;
            gap: 4px;
            padding: 6px 16px;
            background: var(--accent);
            color: #fff;
            border-radius: 20px;
            font-size: 0.78rem;
            font-weight: 500;
            text-decoration: none;
            transition: all 0.2s;
            margin-left: auto;
        }}

        .visit-btn:hover {{
            background: var(--accent-hover);
            transform: scale(1.02);
        }}

        .visit-btn svg {{ width: 12px; height: 12px; }}

        /* ===== Empty State ===== */
        .empty-state {{
            text-align: center;
            padding: 80px 20px;
            color: var(--text-tertiary);
        }}

        .empty-icon {{ font-size: 3rem; margin-bottom: 16px; opacity: 0.4; }}
        .empty-text {{ font-size: 1.1rem; font-weight: 500; }}

        /* ===== Footer ===== */
        .footer {{
            text-align: center;
            padding: 40px 24px 60px;
            border-top: 1px solid var(--border-light);
            margin-top: 60px;
        }}

        .footer p {{
            color: var(--text-tertiary);
            font-size: 0.82rem;
            line-height: 1.7;
        }}

        .admin-link {{
            color: var(--text-tertiary);
            text-decoration: none;
            font-size: 0.78rem;
        }}

        .admin-link:hover {{ color: var(--accent); }}

        /* ===== Error Section ===== */
        .errors-section {{
            max-width: 980px;
            margin: 20px auto;
            padding: 20px 24px;
            background: #fff;
            border-radius: var(--radius);
            border: 1px solid rgba(255,45,85,0.2);
        }}

        .errors-section h3 {{ color: var(--pink); font-size: 0.9rem; font-weight: 600; margin-bottom: 8px; }}
        .errors-section li {{ color: var(--text-secondary); font-size: 0.82rem; padding: 2px 0; }}

        /* ===== Config Info ===== */
        .config-info {{
            max-width: 980px;
            margin: 0 auto 30px;
            padding: 16px 24px;
            background: #f5f5f7;
            border-radius: var(--radius-sm);
            display: flex;
            gap: 24px;
            flex-wrap: wrap;
            font-size: 0.82rem;
            color: var(--text-secondary);
        }}

        .config-info span {{ display: flex; align-items: center; gap: 4px; }}

        /* ===== Responsive ===== */
        @media (max-width: 768px) {{
            .hero {{ padding: 50px 16px 40px; }}
            .hero h1 {{ font-size: 1.8rem; }}
            .stats-bar {{ gap: 24px; padding: 24px 16px; }}
            .stat-number {{ font-size: 2rem; }}
            .result-card {{ padding: 20px 18px; border-radius: 14px; }}
            .card-title {{ font-size: 1rem; padding-right: 0; }}
            .extra-info {{ grid-template-columns: 1fr 1fr; padding: 10px 12px; }}
            .tab-btn {{ padding: 10px 14px; font-size: 0.85rem; }}
            .config-info {{ flex-direction: column; gap: 8px; }}
        }}

        @media (max-width: 480px) {{
            .extra-info {{ grid-template-columns: 1fr; }}
        }}
    </style>
</head>
<body>
    <!-- Hero -->
    <section class="hero">
        <div class="hero-eyebrow">Refractory Bid Search</div>
        <h1>耐火材料招标采购信息日报</h1>
        <p class="hero-date">{today} &nbsp;&middot;&nbsp; 搜索时间 {report.search_time}</p>
    </section>

    <!-- Time Notice -->
    <div class="time-notice">⏰ {expired_note} &middot; 无效链接已标注</div>

    <!-- Stats -->
    <div class="stats-bar">
        <div class="stat-item">
            <div class="stat-number blue">{report.total_results}</div>
            <div class="stat-label">总结果</div>
        </div>
        <div class="stat-item">
            <div class="stat-number orange">{len(bid_results)}</div>
            <div class="stat-label">招标采购</div>
        </div>
        <div class="stat-item">
            <div class="stat-number green">{len(material_results)}</div>
            <div class="stat-label">材料采购</div>
        </div>
        <div class="stat-item">
            <div class="stat-number pink">{len(furnace_results)}</div>
            <div class="stat-label">窑炉维修</div>
        </div>
        <div class="stat-item" style="margin-top:8px">
            <button id="genImgBtn" onclick="generateSummaryImage()" style="
                display:inline-flex;align-items:center;gap:6px;
                padding:10px 22px;border:none;border-radius:22px;
                background:linear-gradient(135deg, #0071e3 0%, #5856d6 100%);
                color:#fff;font-size:0.88rem;font-weight:600;cursor:pointer;
                font-family:var(--font);transition:all 0.3s ease;
                box-shadow:0 4px 15px rgba(0,113,227,0.3);
            " onmouseover="this.style.transform='scale(1.05)';this.style.boxShadow='0 6px 20px rgba(0,113,227,0.4)'" onmouseout="this.style.transform='scale(1)';this.style.boxShadow='0 4px 15px rgba(0,113,227,0.3)'">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><path d="M21 15l-5-5L5 21"/></svg>
                生成今日摘要图片
            </button>
        </div>
    </div>

    <!-- Tabs & Results -->
    <div class="tab-container">
        <div class="config-info">
            <span>🔑 关键词: {report.total_keywords} 个</span>
            <span>📡 搜索源: {len(report.source_stats)} 个</span>
            <span>📊 来源: {' &middot; '.join(f'{k} {v}条' for k,v in report.source_stats.items())}</span>
            {f'<span>⏰ 过期过滤: {report.expired_count} 条</span>' if report.expired_count else ''}
            {f'<span>🔗 无效链接: {report.invalid_links} 条</span>' if report.invalid_links else ''}
        </div>

        <div class="tab-nav">
            <button class="tab-btn active" onclick="switchTab('all')">全部 <span class="count">{report.total_results}</span></button>
            <button class="tab-btn" onclick="switchTab('bid')">招标采购 <span class="count">{len(bid_results)}</span></button>
            <button class="tab-btn" onclick="switchTab('material')">材料采购 <span class="count">{len(material_results)}</span></button>
            <button class="tab-btn" onclick="switchTab('furnace')">窑炉维修 <span class="count">{len(furnace_results)}</span></button>
        </div>

        <div class="results-section active" id="tab-all">
            {_render_results(report.results, "all", article_ids)}
        </div>
        <div class="results-section" id="tab-bid">
            {_render_results(bid_results, "bid", article_ids)}
        </div>
        <div class="results-section" id="tab-material">
            {_render_results(material_results, "material", article_ids)}
        </div>
        <div class="results-section" id="tab-furnace">
            {_render_results(furnace_results, "furnace", article_ids)}
        </div>

        {"".join(_render_errors(report.errors)) if report.errors else ""}
    </div>

    <!-- Footer -->
    <div class="footer">
        <p>耐火材料招标采购信息搜索工具 v3.0 &middot; 每日自动搜索 &middot; 数据仅供参考</p>
        <p>搜索关键词: {report.total_keywords} 个 &middot; 时效: {config.MAX_DAYS_OLD}天内</p>
    </div>

    <script>
        function switchTab(tabName) {{
            document.querySelectorAll('.results-section').forEach(s => s.classList.remove('active'));
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            document.getElementById('tab-' + tabName).classList.add('active');
            event.currentTarget.classList.add('active');
        }}

        // 生成今日摘要图片
        async function generateSummaryImage() {{
            const btn = document.getElementById('genImgBtn');
            const originalHTML = btn.innerHTML;
            btn.innerHTML = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="animation:spin 1s linear infinite"><path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83"/></svg> 生成中...';
            btn.disabled = true;
            btn.style.opacity = '0.7';

            try {{
                const resp = await fetch('/api/summary-image');
                if (!resp.ok) throw new Error('生成失败');
                const blob = await resp.blob();
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = '耐火材料招标日报_' + new Date().toISOString().slice(0,10).replace(/-/g,'') + '.png';
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                URL.revokeObjectURL(url);
                showToast('✅ 摘要图片已生成并下载');
            }} catch (err) {{
                showToast('❌ 生成失败: ' + err.message);
            }} finally {{
                btn.innerHTML = originalHTML;
                btn.disabled = false;
                btn.style.opacity = '1';
            }}
        }}

        // Toast 提示
        function showToast(msg) {{
            let toast = document.getElementById('toast');
            if (!toast) {{
                toast = document.createElement('div');
                toast.id = 'toast';
                toast.style.cssText = 'position:fixed;top:24px;left:50%;transform:translateX(-50%) translateY(-20px);padding:12px 28px;border-radius:14px;font-size:0.9rem;font-weight:500;z-index:9999;opacity:0;transition:all 0.35s ease;font-family:var(--font);backdrop-filter:blur(20px);box-shadow:0 8px 30px rgba(0,0,0,0.12);';
                document.body.appendChild(toast);
            }}
            toast.textContent = msg;
            toast.style.background = msg.includes('✅') ? 'rgba(52,199,89,0.95)' : 'rgba(255,45,85,0.95)';
            toast.style.color = '#fff';
            toast.style.opacity = '1';
            toast.style.transform = 'translateX(-50%) translateY(0)';
            setTimeout(() => {{
                toast.style.opacity = '0';
                toast.style.transform = 'translateX(-50%) translateY(-20px)';
            }}, 3000);
        }}

        document.addEventListener('DOMContentLoaded', function() {{
            const observer = new IntersectionObserver((entries) => {{
                entries.forEach(entry => {{
                    if (entry.isIntersecting) {{
                        entry.target.style.opacity = '1';
                        entry.target.style.transform = 'translateY(0)';
                        observer.unobserve(entry.target);
                    }}
                }});
            }}, {{ threshold: 0.1 }});

            document.querySelectorAll('.result-card').forEach(card => {{
                card.style.opacity = '0';
                card.style.transform = 'translateY(16px)';
                card.style.transition = 'opacity 0.5s ease, transform 0.5s ease';
                observer.observe(card);
            }});
        }});
    </script>
    <style>@keyframes spin{{from{{transform:rotate(0deg)}}to{{transform:rotate(360deg)}}}}</style>
</body>
</html>"""

    if return_html:
        return html

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(html)

    # 同时复制到 docs 目录用于 GitHub Pages
    docs_dir = os.path.join(_get_app_dir(), "docs")
    os.makedirs(docs_dir, exist_ok=True)
    docs_path = os.path.join(docs_dir, "index.html")
    with open(docs_path, "w", encoding="utf-8") as f:
        f.write(html)

    return filepath


def _render_results(results: List[SearchResult], category: str, article_ids: Dict[str, str] = None) -> str:
    if not results:
        return """
        <div class="empty-state">
            <div class="empty-icon">📭</div>
            <div class="empty-text">暂无此类结果</div>
        </div>"""

    if article_ids is None:
        article_ids = {}

    cards = []
    for r in results:
        cat_class = f"cat-{_get_cat_class(r.category)}"
        tag_class = f"tag-{_get_cat_class(r.category)}"
        score_class = "high" if r.relevance_score >= 70 else ("mid" if r.relevance_score >= 40 else "")

        # 链接无效标记
        link_invalid_class = " link-invalid" if r.link_valid is False else ""

        # 构建额外信息区域
        extra_html = _build_extra_info(r)

        # 时效标签
        fresh_tag = ""
        if r.date:
            try:
                from datetime import datetime as dt
                pub = dt.strptime(r.date[:10], "%Y-%m-%d")
                days = (dt.now() - pub).days
                if days <= 3:
                    fresh_tag = '<span class="tag tag-fresh">🆕 3天内</span>'
                elif days <= 7:
                    fresh_tag = '<span class="tag tag-fresh">本周</span>'
            except:
                pass

        # 联系方式标签
        contact_tag = ""
        if r.contact:
            contact_tag = f'<span class="tag tag-contact">📞 {_esc(r.contact)}</span>'

        # 生成可点击URL（对无效URL走Flask跳转代理）
        article_id = article_ids.get(r.url, "")
        click_url = _make_click_url(r.url, article_id)

        # 构建跳转按钮
        visit_btn = f"""<a href="{_esc(click_url)}" target="_blank" rel="noopener" class="visit-btn">
            查看详情 <svg viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M2 6h8M7 3l3 3-3 3"/></svg>
        </a>"""

        card = f"""
        <div class="result-card {cat_class}{link_invalid_class}">
            <div class="card-title">
                <a href="{_esc(click_url)}" target="_blank" rel="noopener">{_esc(r.title)}</a>
            </div>
            <div class="card-snippet">{_esc(r.snippet)}</div>
            {extra_html}
            <div class="card-meta">
                <span class="tag {tag_class}">{r.category}</span>
                <span class="tag tag-score {score_class}">{r.relevance_score:.0f}分</span>
                <span class="tag tag-source">{_esc(r.source)}</span>
                <span class="tag tag-keyword">{_esc(r.keyword)}</span>
                {fresh_tag}
                {contact_tag}
                {f'<span class="tag tag-date">{_esc(r.date)}</span>' if r.date else ''}
                {visit_btn}
            </div>
        </div>"""
        cards.append(card)

    return "".join(cards)


def _build_extra_info(r: SearchResult) -> str:
    items = []
    if r.budget:
        items.append(f'<div class="extra-item"><span class="label">💰 预算:</span><span class="value budget">{_esc(r.budget)}</span></div>')
    if r.deadline:
        items.append(f'<div class="extra-item"><span class="label">⏰ 截止:</span><span class="value deadline">{_esc(r.deadline)}</span></div>')
    if r.publisher:
        items.append(f'<div class="extra-item"><span class="label">🏢 采购方:</span><span class="value">{_esc(r.publisher)}</span></div>')
    if r.region:
        items.append(f'<div class="extra-item"><span class="label">📍 地区:</span><span class="value">{_esc(r.region)}</span></div>')
    if r.bid_type:
        items.append(f'<div class="extra-item"><span class="label">📋 类型:</span><span class="value">{_esc(r.bid_type)}</span></div>')
    if r.contact:
        items.append(f'<div class="extra-item"><span class="label">📞 联系:</span><span class="value">{_esc(r.contact)}</span></div>')
    if r.domain:
        items.append(f'<div class="extra-item"><span class="label">🌐 来源:</span><span class="value">{_esc(r.domain)}</span></div>')

    if not items:
        return ""

    return f'<div class="extra-info">{"".join(items)}</div>'


def _render_errors(errors: List[str]) -> List[str]:
    if not errors:
        return []
    items = [f"<li>{_esc(e)}</li>" for e in errors]
    return [f"""
    <div class="errors-section">
        <h3>⚠️ 搜索过程中的错误 ({len(errors)})</h3>
        <ul>{"".join(items)}</ul>
    </div>"""]


def _get_cat_class(category: str) -> str:
    return {"招标采购": "bid", "材料采购": "material", "窑炉维修": "furnace"}.get(category, "bid")


def _esc(text: str) -> str:
    if not text:
        return ""
    return (text
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&#x27;"))
