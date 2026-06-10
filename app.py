"""
耐火材料招标采购信息搜索工具 - Flask Web 服务器 v3.0
前台：苹果风格报告展示
后台：登录认证 + 文章管理 + 即时更新 + 关键词管理 + API管理
"""

import os
import sys
import json
import sqlite3
import threading
import logging
from datetime import datetime, timedelta
from functools import wraps

# 修复 Windows UTF-8
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

def _get_app_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

sys.path.insert(0, _get_app_dir())

from flask import Flask, request, jsonify, session, send_from_directory, render_template_string, redirect, send_file
from werkzeug.utils import secure_filename

import config
from search_engine import SearchScheduler, SearchResult, SearchReport, LinkValidator
from report_generator import generate_html_report

logger = logging.getLogger(__name__)

# ==================== Flask App ====================

app = Flask(__name__)
app.secret_key = os.urandom(24).hex()

# 全局搜索状态
_search_status = {
    "running": False,
    "progress": "",
    "last_update": None,
    "result_count": 0,
    "error": None,
}

# ==================== 数据库 ====================

def _db_path():
    return os.path.join(_get_app_dir(), config.DB_NAME)

def _get_db():
    db = sqlite3.connect(_db_path())
    db.row_factory = sqlite3.Row
    return db

def init_db():
    db = _get_db()
    db.executescript("""
        CREATE TABLE IF NOT EXISTS articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            url TEXT DEFAULT '',
            snippet TEXT DEFAULT '',
            snippet_full TEXT DEFAULT '',
            source TEXT DEFAULT '',
            keyword TEXT DEFAULT '',
            date TEXT DEFAULT '',
            category TEXT DEFAULT '',
            relevance_score REAL DEFAULT 0,
            publisher TEXT DEFAULT '',
            budget TEXT DEFAULT '',
            deadline TEXT DEFAULT '',
            region TEXT DEFAULT '',
            bid_type TEXT DEFAULT '',
            contact TEXT DEFAULT '',
            domain TEXT DEFAULT '',
            link_valid INTEGER DEFAULT NULL,
            is_manual INTEGER DEFAULT 0,
            is_deleted INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now', 'localtime')),
            updated_at TEXT DEFAULT (datetime('now', 'localtime'))
        );
        CREATE INDEX IF NOT EXISTS idx_articles_date ON articles(date);
        CREATE INDEX IF NOT EXISTS idx_articles_category ON articles(category);
        CREATE INDEX IF NOT EXISTS idx_articles_deleted ON articles(is_deleted);
    """)
    db.commit()
    db.close()

def save_report_to_db(report: SearchReport):
    """将搜索报告保存到数据库"""
    db = _get_db()
    cutoff = (datetime.now() - timedelta(days=config.MAX_DAYS_OLD)).strftime("%Y-%m-%d")

    # 软删除旧的自动抓取文章
    db.execute("UPDATE articles SET is_deleted = 1 WHERE is_manual = 0 AND date < ?", (cutoff,))
    db.execute("UPDATE articles SET is_deleted = 1 WHERE is_manual = 0")

    for r in report.results:
        # 检查是否已存在（根据URL去重）
        existing = db.execute("SELECT id FROM articles WHERE url = ? AND is_deleted = 0", (r.url,)).fetchone()
        if existing:
            # 更新
            db.execute("""
                UPDATE articles SET title=?, snippet=?, snippet_full=?, source=?, keyword=?,
                    date=?, category=?, relevance_score=?, publisher=?, budget=?, deadline=?,
                    region=?, bid_type=?, contact=?, domain=?, link_valid=?, updated_at=?
                WHERE id=?
            """, (r.title, r.snippet, r.snippet_full, r.source, r.keyword,
                  r.date, r.category, r.relevance_score, r.publisher, r.budget, r.deadline,
                  r.region, r.bid_type, r.contact, r.domain,
                  1 if r.link_valid else (0 if r.link_valid is False else None),
                  datetime.now().strftime("%Y-%m-%d %H:%M:%S"), existing['id']))
        else:
            # 插入
            db.execute("""
                INSERT INTO articles (title, url, snippet, snippet_full, source, keyword, date,
                    category, relevance_score, publisher, budget, deadline, region, bid_type,
                    contact, domain, link_valid)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (r.title, r.url, r.snippet, r.snippet_full, r.source, r.keyword, r.date,
                  r.category, r.relevance_score, r.publisher, r.budget, r.deadline, r.region,
                  r.bid_type, r.contact, r.domain,
                  1 if r.link_valid else (0 if r.link_valid is False else None)))

    db.commit()
    db.close()

def get_articles_from_db(category=None, keyword=None, page=1, per_page=50, include_deleted=False):
    """从数据库获取文章"""
    db = _get_db()
    where = "1=1"
    params = []

    if not include_deleted:
        where += " AND is_deleted = 0"
    if category and category != "all":
        where += " AND category = ?"
        params.append(category)
    if keyword:
        where += " AND (title LIKE ? OR snippet LIKE ? OR publisher LIKE ?)"
        params.extend([f"%{keyword}%"] * 3)

    # 计算总数
    total = db.execute(f"SELECT COUNT(*) FROM articles WHERE {where}", params).fetchone()[0]

    # 分页
    offset = (page - 1) * per_page
    rows = db.execute(
        f"SELECT * FROM articles WHERE {where} ORDER BY date DESC, relevance_score DESC LIMIT ? OFFSET ?",
        params + [per_page, offset]
    ).fetchall()

    db.close()
    return [dict(r) for r in rows], total


# ==================== 认证装饰器 ====================

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("admin_logged_in"):
            return jsonify({"error": "未登录"}), 401
        return f(*args, **kwargs)
    return decorated


# ==================== 前台路由 ====================

@app.route("/")
def index():
    """前台：苹果风格报告页面"""
    db = _get_db()
    cutoff = (datetime.now() - timedelta(days=config.MAX_DAYS_OLD)).strftime("%Y-%m-%d")

    # 统计数据
    stats = db.execute("""
        SELECT category, COUNT(*) as cnt FROM articles
        WHERE is_deleted = 0 AND date >= ? AND (link_valid IS NULL OR link_valid = 1)
        GROUP BY category
    """, (cutoff,)).fetchall()

    category_stats = {row['category']: row['cnt'] for row in stats}
    total = sum(category_stats.values())

    # 获取所有有效文章
    rows = db.execute("""
        SELECT * FROM articles
        WHERE is_deleted = 0 AND date >= ?
        ORDER BY relevance_score DESC, date DESC
    """, (cutoff,)).fetchall()

    articles = [dict(r) for r in rows]
    db.close()

    # 构建报告对象供模板使用
    report = SearchReport(
        search_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        total_results=total,
        category_stats=category_stats,
    )
    results = []
    # 构建 url -> article_id 映射，用于跳转代理
    article_ids = {}
    for a in articles:
        r = SearchResult(
            title=a['title'], url=a['url'], snippet=a['snippet'],
            source=a['source'], keyword=a['keyword'], date=a['date'],
            category=a['category'], relevance_score=a['relevance_score'],
            publisher=a['publisher'], budget=a['budget'], deadline=a['deadline'],
            region=a['region'], bid_type=a['bid_type'], contact=a['contact'],
            domain=a['domain'], snippet_full=a.get('snippet_full', a['snippet']),
            link_valid=True if a['link_valid'] == 1 else (False if a['link_valid'] == 0 else None),
        )
        results.append(r)
        if a.get('id'):
            article_ids[a['url']] = str(a['id'])
    report.results = results

    from report_generator import generate_html_report
    html = generate_html_report(report, return_html=True, article_ids=article_ids)
    return html


@app.route("/api/summary-image")
def api_summary_image():
    """生成并返回今日摘要卡片图片"""
    from image_generator import generate_summary_image
    try:
        img_buf = generate_summary_image()
        return send_file(img_buf, mimetype='image/png', as_attachment=True,
                         download_name=f'耐火材料招标日报_{datetime.now().strftime("%Y%m%d")}.png')
    except Exception as e:
        logger.error(f"生成摘要图片失败: {e}")
        return jsonify({"error": f"生成图片失败: {str(e)}"}), 500


@app.route("/reports/<path:filename>")
def serve_report(filename):
    return send_from_directory(os.path.join(_get_app_dir(), config.REPORT_DIR), filename)


@app.route("/go")
def go_redirect():
    """URL跳转代理 - 对于百度加密token等无法直接访问的URL，通过服务器端跟踪重定向"""
    import requests as req
    url = request.args.get("url", "")
    article_id = request.args.get("id", "")

    if not url:
        return "缺少URL参数", 400

    # 如果已经是有效的http链接，直接重定向
    if url.startswith("http://") or url.startswith("https://"):
        # 对于百度重定向链接，尝试跟踪获取真实URL
        if "baidu.com/link" in url or "baidu.com/baidu.php" in url:
            try:
                resp = req.head(url, timeout=8, allow_redirects=True, headers=config.HEADERS)
                if resp.url and "baidu.com" not in resp.url:
                    # 更新数据库中的URL
                    if article_id:
                        _update_article_url(article_id, resp.url)
                    return redirect(resp.url)
            except Exception:
                pass
            try:
                resp = req.get(url, timeout=8, allow_redirects=True, headers=config.HEADERS, stream=True)
                resp.close()
                if resp.url and "baidu.com" not in resp.url:
                    if article_id:
                        _update_article_url(article_id, resp.url)
                    return redirect(resp.url)
            except Exception:
                pass
        return redirect(url)

    # 对于非http的加密token，尝试构造成百度重定向URL再跟踪
    baidu_url = f"https://www.baidu.com/link?url={url}"
    try:
        resp = req.head(baidu_url, timeout=8, allow_redirects=True, headers=config.HEADERS)
        if resp.url and "baidu.com" not in resp.url:
            if article_id:
                _update_article_url(article_id, resp.url)
            return redirect(resp.url)
    except Exception:
        pass
    try:
        resp = req.get(baidu_url, timeout=8, allow_redirects=True, headers=config.HEADERS, stream=True)
        resp.close()
        if resp.url and "baidu.com" not in resp.url:
            if article_id:
                _update_article_url(article_id, resp.url)
            return redirect(resp.url)
    except Exception:
        pass

    # 所有方法都失败了，显示错误页面
    return render_template_string("""
    <!DOCTYPE html><html><head><meta charset="utf-8"><title>链接跳转</title>
    <style>body{font-family:-apple-system,sans-serif;display:flex;justify-content:center;align-items:center;min-height:100vh;margin:0;background:#f5f5f7;color:#1d1d1f}
    .box{text-align:center;padding:40px;background:#fff;border-radius:16px;box-shadow:0 2px 12px rgba(0,0,0,0.06)}
    h2{font-size:1.3rem;margin-bottom:12px}p{color:#6e6e73;font-size:0.9rem;margin-bottom:20px}
    a{color:#0071e3;text-decoration:none}a:hover{text-decoration:underline}</style></head>
    <body><div class="box">
    <h2>⚠️ 链接暂时无法访问</h2>
    <p>该链接可能已过期或来源网站不可达</p>
    <p><a href="javascript:history.back()">← 返回上一页</a></p>
    </div></body></html>
    """), 502


def _update_article_url(article_id, new_url):
    """更新数据库中文章的URL为真实URL"""
    try:
        db = _get_db()
        db.execute("UPDATE articles SET url = ?, updated_at = ? WHERE id = ?",
                  (new_url, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), int(article_id)))
        db.commit()
        db.close()
        logger.info(f"已更新文章 {article_id} 的URL: {new_url[:80]}")
    except Exception as e:
        logger.warning(f"更新URL失败: {e}")


# ==================== 后台路由 ====================

@app.route("/admin")
def admin_page():
    """后台管理页面"""
    return render_template_string(ADMIN_HTML)


@app.route("/api/login", methods=["POST"])
def api_login():
    data = request.get_json() or {}
    username = data.get("username", "")
    password = data.get("password", "")

    if username == config.ADMIN_USERNAME and password == config.ADMIN_PASSWORD:
        session["admin_logged_in"] = True
        session.permanent = True
        return jsonify({"success": True})
    return jsonify({"error": "用户名或密码错误"}), 401


@app.route("/api/logout", methods=["POST"])
def api_logout():
    session.clear()
    return jsonify({"success": True})


@app.route("/api/check-auth")
def api_check_auth():
    return jsonify({"logged_in": session.get("admin_logged_in", False)})


@app.route("/api/articles")
@admin_required
def api_articles():
    category = request.args.get("category", "all")
    keyword = request.args.get("keyword", "")
    page = int(request.args.get("page", 1))
    per_page = int(request.args.get("per_page", 30))

    articles, total = get_articles_from_db(category, keyword, page, per_page)
    return jsonify({
        "articles": articles,
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": (total + per_page - 1) // per_page,
    })


@app.route("/api/articles/<int:article_id>", methods=["PUT"])
@admin_required
def api_update_article(article_id):
    data = request.get_json() or {}
    db = _get_db()

    fields = ["title", "snippet", "snippet_full", "publisher", "budget", "deadline",
              "region", "bid_type", "contact", "category", "date", "url"]
    updates = []
    params = []
    for f in fields:
        if f in data:
            updates.append(f"{f} = ?")
            params.append(data[f])

    if updates:
        updates.append("updated_at = ?")
        params.append(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        params.append(article_id)
        db.execute(f"UPDATE articles SET {', '.join(updates)} WHERE id = ?", params)
        db.commit()

    db.close()
    return jsonify({"success": True})


@app.route("/api/articles/<int:article_id>", methods=["DELETE"])
@admin_required
def api_delete_article(article_id):
    db = _get_db()
    db.execute("UPDATE articles SET is_deleted = 1, updated_at = ? WHERE id = ?",
              (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), article_id))
    db.commit()
    db.close()
    return jsonify({"success": True})


@app.route("/api/articles", methods=["POST"])
@admin_required
def api_add_article():
    data = request.get_json() or {}
    db = _get_db()
    db.execute("""
        INSERT INTO articles (title, url, snippet, source, keyword, date, category,
            relevance_score, publisher, budget, deadline, region, bid_type, contact,
            domain, link_valid, is_manual)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,1)
    """, (
        data.get("title", ""),
        data.get("url", ""),
        data.get("snippet", ""),
        "手动添加",
        data.get("keyword", ""),
        data.get("date", datetime.now().strftime("%Y-%m-%d")),
        data.get("category", "招标采购"),
        data.get("relevance_score", 80),
        data.get("publisher", ""),
        data.get("budget", ""),
        data.get("deadline", ""),
        data.get("region", ""),
        data.get("bid_type", ""),
        data.get("contact", ""),
        "",
        1,
    ))
    db.commit()
    db.close()
    return jsonify({"success": True})


@app.route("/api/update", methods=["POST"])
@admin_required
def api_trigger_update():
    """即时更新：触发搜索"""
    global _search_status

    if _search_status["running"]:
        return jsonify({"error": "搜索正在进行中"}), 409

    # 启动后台搜索线程
    thread = threading.Thread(target=_run_background_search, daemon=True)
    thread.start()

    return jsonify({"success": True, "message": "搜索已开始"})


@app.route("/api/status")
@admin_required
def api_search_status():
    return jsonify(_search_status)


@app.route("/api/keywords", methods=["GET"])
@admin_required
def api_get_keywords():
    keywords = config.ConfigManager.get_keywords()
    return jsonify({"keywords": keywords})


@app.route("/api/keywords", methods=["POST"])
@admin_required
def api_set_keywords():
    data = request.get_json() or {}
    keywords = data.get("keywords", [])
    config.ConfigManager.set_keywords(keywords)
    return jsonify({"success": True})


@app.route("/api/api-sources", methods=["GET"])
@admin_required
def api_get_sources():
    sources = config.ConfigManager.get_api_sources()
    return jsonify({"sources": sources})


@app.route("/api/api-sources", methods=["POST"])
@admin_required
def api_add_source():
    data = request.get_json() or {}
    key = data.get("key", "")
    source_cfg = data.get("config", {})
    if not key:
        return jsonify({"error": "缺少数据源标识"}), 400
    config.ConfigManager.add_api_source(key, source_cfg)
    return jsonify({"success": True})


@app.route("/api/api-sources/<key>", methods=["DELETE"])
@admin_required
def api_delete_source(key):
    config.ConfigManager.remove_api_source(key)
    return jsonify({"success": True})


@app.route("/api/api-sources/<key>/toggle", methods=["POST"])
@admin_required
def api_toggle_source(key):
    data = request.get_json() or {}
    enabled = data.get("enabled", True)
    config.ConfigManager.toggle_api_source(key, enabled)
    return jsonify({"success": True})


@app.route("/api/validate-links", methods=["POST"])
@admin_required
def api_validate_links():
    """手动触发链接验证"""
    thread = threading.Thread(target=_run_link_validation, daemon=True)
    thread.start()
    return jsonify({"success": True, "message": "链接验证已开始"})


@app.route("/api/stats")
@admin_required
def api_stats():
    db = _get_db()
    cutoff = (datetime.now() - timedelta(days=config.MAX_DAYS_OLD)).strftime("%Y-%m-%d")

    total = db.execute("SELECT COUNT(*) FROM articles WHERE is_deleted = 0 AND date >= ?", (cutoff,)).fetchone()[0]
    valid_links = db.execute("SELECT COUNT(*) FROM articles WHERE is_deleted = 0 AND link_valid = 1 AND date >= ?", (cutoff,)).fetchone()[0]
    invalid_links = db.execute("SELECT COUNT(*) FROM articles WHERE is_deleted = 0 AND link_valid = 0 AND date >= ?", (cutoff,)).fetchone()[0]
    manual = db.execute("SELECT COUNT(*) FROM articles WHERE is_deleted = 0 AND is_manual = 1 AND date >= ?", (cutoff,)).fetchone()[0]

    categories = db.execute("""
        SELECT category, COUNT(*) as cnt FROM articles
        WHERE is_deleted = 0 AND date >= ?
        GROUP BY category
    """, (cutoff,)).fetchall()

    db.close()

    return jsonify({
        "total": total,
        "valid_links": valid_links,
        "invalid_links": invalid_links,
        "manual_count": manual,
        "categories": {r['category']: r['cnt'] for r in categories},
    })


# ==================== 后台搜索 ====================

def _run_background_search():
    global _search_status
    _search_status["running"] = True
    _search_status["progress"] = "正在搜索..."
    _search_status["error"] = None

    try:
        keywords = config.ConfigManager.get_keywords()
        _search_status["progress"] = f"正在搜索 {len(keywords)} 个关键词..."

        scheduler = SearchScheduler()
        report = scheduler.run_search(keywords, validate_links=True)

        _search_status["progress"] = "正在保存到数据库..."
        save_report_to_db(report)

        # 同时生成静态 HTML 报告
        _search_status["progress"] = "正在生成报告..."
        generate_html_report(report)

        _search_status["result_count"] = report.total_results
        _search_status["last_update"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        _search_status["progress"] = "完成"
        logger.info(f"✅ 后台搜索完成: {report.total_results} 条结果")

    except Exception as e:
        _search_status["error"] = str(e)
        _search_status["progress"] = f"搜索出错: {e}"
        logger.error(f"❌ 后台搜索失败: {e}")

    finally:
        _search_status["running"] = False


def _run_link_validation():
    """后台验证所有未验证的链接"""
    db = _get_db()
    rows = db.execute("""
        SELECT id, url FROM articles
        WHERE is_deleted = 0 AND link_valid IS NULL AND url != ''
    """).fetchall()
    db.close()

    logger.info(f"🔍 开始验证 {len(rows)} 条链接...")

    for row in rows:
        valid = LinkValidator.validate(row['url'])
        db = _get_db()
        db.execute("UPDATE articles SET link_valid = ? WHERE id = ?",
                  (1 if valid else 0, row['id']))
        db.commit()
        db.close()

    logger.info("✅ 链接验证完成")


# ==================== 后台管理页面 HTML ====================

ADMIN_HTML = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>耐火材料招标 - 后台管理</title>
    <style>
        :root {
            --bg: #f5f5f7;
            --card: #fff;
            --text: #1d1d1f;
            --text2: #6e6e73;
            --text3: #86868b;
            --border: #d2d2d7;
            --border-light: #e8e8ed;
            --accent: #0071e3;
            --accent-hover: #0077ed;
            --green: #34c759;
            --orange: #ff9500;
            --pink: #ff2d55;
            --radius: 14px;
            --shadow: 0 2px 12px rgba(0,0,0,0.06);
        }
        * { margin:0; padding:0; box-sizing:border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display", "PingFang SC", "Microsoft YaHei", sans-serif; background: var(--bg); color: var(--text); }

        /* Login */
        .login-wrap { display:flex; justify-content:center; align-items:center; min-height:100vh; }
        .login-box { background:var(--card); border-radius:20px; padding:48px 40px; box-shadow:var(--shadow); width:360px; text-align:center; }
        .login-box h2 { font-size:1.4rem; margin-bottom:8px; }
        .login-box p { color:var(--text3); font-size:0.85rem; margin-bottom:28px; }
        .login-box input { width:100%; padding:12px 16px; border:1px solid var(--border); border-radius:10px; font-size:0.95rem; margin-bottom:12px; outline:none; font-family:inherit; }
        .login-box input:focus { border-color:var(--accent); box-shadow:0 0 0 3px rgba(0,113,227,0.12); }
        .login-box button { width:100%; padding:12px; background:var(--accent); color:#fff; border:none; border-radius:10px; font-size:1rem; font-weight:600; cursor:pointer; font-family:inherit; }
        .login-box button:hover { background:var(--accent-hover); }
        .login-error { color:var(--pink); font-size:0.85rem; margin-top:12px; display:none; }

        /* Dashboard */
        .dashboard { display:none; }
        .topbar { background:var(--card); border-bottom:1px solid var(--border-light); padding:12px 24px; display:flex; align-items:center; justify-content:space-between; position:sticky; top:0; z-index:100; }
        .topbar h1 { font-size:1.1rem; font-weight:600; }
        .topbar-actions { display:flex; gap:8px; align-items:center; }

        .btn { padding:8px 16px; border-radius:20px; border:none; font-size:0.82rem; font-weight:500; cursor:pointer; font-family:inherit; transition:all 0.2s; }
        .btn-primary { background:var(--accent); color:#fff; }
        .btn-primary:hover { background:var(--accent-hover); }
        .btn-primary:disabled { opacity:0.5; cursor:not-allowed; }
        .btn-outline { background:none; border:1px solid var(--border); color:var(--text2); }
        .btn-outline:hover { background:var(--bg); }
        .btn-danger { background:var(--pink); color:#fff; }
        .btn-danger:hover { opacity:0.9; }
        .btn-success { background:var(--green); color:#fff; }
        .btn-sm { padding:5px 12px; font-size:0.78rem; }

        .container { max-width:1200px; margin:0 auto; padding:20px 24px; }

        /* Stats Cards */
        .stats-grid { display:grid; grid-template-columns:repeat(auto-fit, minmax(180px,1fr)); gap:12px; margin-bottom:24px; }
        .stat-card { background:var(--card); border-radius:var(--radius); padding:20px; box-shadow:var(--shadow); }
        .stat-card .num { font-size:2rem; font-weight:700; }
        .stat-card .num.blue { color:var(--accent); }
        .stat-card .num.green { color:var(--green); }
        .stat-card .num.orange { color:var(--orange); }
        .stat-card .num.pink { color:var(--pink); }
        .stat-card .label { font-size:0.82rem; color:var(--text3); margin-top:4px; }

        /* Update Status */
        .update-bar { background:var(--card); border-radius:var(--radius); padding:16px 20px; margin-bottom:20px; display:flex; align-items:center; gap:16px; box-shadow:var(--shadow); }
        .update-bar .status-dot { width:8px; height:8px; border-radius:50%; }
        .update-bar .status-dot.idle { background:var(--green); }
        .update-bar .status-dot.running { background:var(--orange); animation:pulse 1.5s infinite; }
        @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.4} }
        .update-bar .info { flex:1; }
        .update-bar .info .time { font-size:0.78rem; color:var(--text3); }

        /* Filter Bar */
        .filter-bar { display:flex; gap:8px; margin-bottom:16px; flex-wrap:wrap; align-items:center; }
        .filter-bar select, .filter-bar input { padding:8px 12px; border:1px solid var(--border); border-radius:8px; font-size:0.85rem; outline:none; font-family:inherit; }
        .filter-bar select:focus, .filter-bar input:focus { border-color:var(--accent); }

        /* Article Table */
        .table-wrap { background:var(--card); border-radius:var(--radius); box-shadow:var(--shadow); overflow:hidden; }
        table { width:100%; border-collapse:collapse; font-size:0.85rem; }
        th { background:#f5f5f7; padding:12px 16px; text-align:left; font-weight:600; color:var(--text2); font-size:0.78rem; text-transform:uppercase; letter-spacing:0.03em; border-bottom:1px solid var(--border-light); }
        td { padding:12px 16px; border-bottom:1px solid var(--border-light); vertical-align:top; }
        tr:hover { background:#fafafa; }
        .title-cell { max-width:320px; font-weight:500; }
        .title-cell a { color:var(--text); text-decoration:none; }
        .title-cell a:hover { color:var(--accent); }
        .tag { display:inline-block; padding:2px 8px; border-radius:10px; font-size:0.72rem; font-weight:500; }
        .tag-bid { background:rgba(0,113,227,0.08); color:var(--accent); }
        .tag-material { background:rgba(52,199,89,0.08); color:var(--green); }
        .tag-furnace { background:rgba(255,45,85,0.08); color:var(--pink); }
        .link-ok { color:var(--green); }
        .link-bad { color:var(--pink); }
        .link-unknown { color:var(--text3); }

        .pagination { display:flex; justify-content:center; gap:4px; margin-top:16px; }
        .pagination button { padding:6px 12px; border:1px solid var(--border); border-radius:6px; background:var(--card); cursor:pointer; font-size:0.82rem; }
        .pagination button.active { background:var(--accent); color:#fff; border-color:var(--accent); }
        .pagination button:disabled { opacity:0.4; }

        /* Modal */
        .modal-overlay { display:none; position:fixed; inset:0; background:rgba(0,0,0,0.4); z-index:200; justify-content:center; align-items:center; }
        .modal-overlay.show { display:flex; }
        .modal { background:var(--card); border-radius:20px; padding:32px; width:500px; max-width:90vw; max-height:80vh; overflow-y:auto; }
        .modal h3 { font-size:1.1rem; margin-bottom:20px; }
        .modal label { display:block; font-size:0.82rem; font-weight:500; color:var(--text2); margin-bottom:4px; margin-top:12px; }
        .modal input, .modal select, .modal textarea { width:100%; padding:8px 12px; border:1px solid var(--border); border-radius:8px; font-size:0.9rem; outline:none; font-family:inherit; }
        .modal textarea { min-height:80px; resize:vertical; }
        .modal-actions { display:flex; gap:8px; justify-content:flex-end; margin-top:20px; }

        /* Tabs */
        .tab-nav { display:flex; gap:4px; margin-bottom:16px; }
        .tab-nav button { padding:8px 16px; border:none; background:none; color:var(--text2); cursor:pointer; font-size:0.9rem; font-weight:500; border-bottom:2px solid transparent; font-family:inherit; }
        .tab-nav button.active { color:var(--accent); border-bottom-color:var(--accent); }

        .tab-content { display:none; }
        .tab-content.active { display:block; }

        /* Keywords list */
        .kw-list { display:flex; flex-wrap:wrap; gap:6px; margin-top:12px; }
        .kw-chip { display:inline-flex; align-items:center; gap:4px; padding:4px 12px; background:#f0f0f5; border-radius:16px; font-size:0.82rem; }
        .kw-chip .remove { cursor:pointer; color:var(--text3); font-weight:700; }
        .kw-chip .remove:hover { color:var(--pink); }
    </style>
</head>
<body>

<!-- Login Page -->
<div class="login-wrap" id="loginPage">
    <div class="login-box">
        <h2>后台管理</h2>
        <p>耐火材料招标采购信息管理系统</p>
        <input type="text" id="username" placeholder="用户名" autocomplete="username">
        <input type="password" id="password" placeholder="密码" autocomplete="current-password">
        <button onclick="doLogin()">登 录</button>
        <div class="login-error" id="loginError">用户名或密码错误</div>
    </div>
</div>

<!-- Dashboard -->
<div class="dashboard" id="dashboard">
    <div class="topbar">
        <h1>耐火材料招标 - 后台管理</h1>
        <div class="topbar-actions">
            <a href="/" target="_blank" class="btn btn-outline btn-sm">查看前台</a>
            <button class="btn btn-outline btn-sm" onclick="doLogout()">退出登录</button>
        </div>
    </div>

    <div class="container">
        <!-- Stats -->
        <div class="stats-grid" id="statsGrid">
            <div class="stat-card"><div class="num blue" id="statTotal">-</div><div class="label">总资讯数</div></div>
            <div class="stat-card"><div class="num green" id="statValid">-</div><div class="label">有效链接</div></div>
            <div class="stat-card"><div class="num orange" id="statInvalid">-</div><div class="label">无效链接</div></div>
            <div class="stat-card"><div class="num pink" id="statManual">-</div><div class="label">手动添加</div></div>
        </div>

        <!-- Update Bar -->
        <div class="update-bar">
            <div class="status-dot idle" id="statusDot"></div>
            <div class="info">
                <div id="statusText">就绪</div>
                <div class="time" id="lastUpdateTime">上次更新: -</div>
            </div>
            <button class="btn btn-primary" id="updateBtn" onclick="triggerUpdate()">🔄 即时更新</button>
            <button class="btn btn-outline" onclick="validateLinks()">🔗 验证链接</button>
        </div>

        <!-- Tab Nav -->
        <div class="tab-nav">
            <button class="active" onclick="switchAdminTab('articles')">资讯管理</button>
            <button onclick="switchAdminTab('keywords')">关键词管理</button>
            <button onclick="switchAdminTab('apis')">API数据源</button>
        </div>

        <!-- Articles Tab -->
        <div class="tab-content active" id="tab-articles">
            <div class="filter-bar">
                <select id="filterCategory" onchange="loadArticles()">
                    <option value="all">全部分类</option>
                    <option value="招标采购">招标采购</option>
                    <option value="材料采购">材料采购</option>
                    <option value="窑炉维修">窑炉维修</option>
                </select>
                <input type="text" id="filterKeyword" placeholder="搜索标题/内容..." onkeydown="if(event.key==='Enter')loadArticles()">
                <button class="btn btn-outline btn-sm" onclick="loadArticles()">搜索</button>
                <button class="btn btn-success btn-sm" onclick="showAddModal()">+ 手动添加</button>
            </div>

            <div class="table-wrap">
                <table>
                    <thead>
                        <tr>
                            <th>标题</th>
                            <th>日期</th>
                            <th>分类</th>
                            <th>来源</th>
                            <th>链接</th>
                            <th>操作</th>
                        </tr>
                    </thead>
                    <tbody id="articlesBody"></tbody>
                </table>
            </div>

            <div class="pagination" id="pagination"></div>
        </div>

        <!-- Keywords Tab -->
        <div class="tab-content" id="tab-keywords">
            <div style="display:flex;gap:8px;margin-bottom:12px;">
                <input type="text" id="newKeyword" placeholder="输入新关键词..." style="flex:1;padding:8px 12px;border:1px solid var(--border);border-radius:8px;">
                <button class="btn btn-primary btn-sm" onclick="addKeyword()">添加</button>
            </div>
            <div class="kw-list" id="keywordsList"></div>
        </div>

        <!-- APIs Tab -->
        <div class="tab-content" id="tab-apis">
            <div id="apisList"></div>
        </div>
    </div>
</div>

<!-- Add/Edit Modal -->
<div class="modal-overlay" id="articleModal">
    <div class="modal">
        <h3 id="modalTitle">添加资讯</h3>
        <input type="hidden" id="editId">
        <label>标题 *</label>
        <input type="text" id="mTitle">
        <label>链接 URL</label>
        <input type="text" id="mUrl">
        <label>分类</label>
        <select id="mCategory">
            <option value="招标采购">招标采购</option>
            <option value="材料采购">材料采购</option>
            <option value="窑炉维修">窑炉维修</option>
        </select>
        <label>摘要</label>
        <textarea id="mSnippet"></textarea>
        <label>发布单位</label>
        <input type="text" id="mPublisher">
        <label>预算金额</label>
        <input type="text" id="mBudget">
        <label>截止日期</label>
        <input type="text" id="mDeadline" placeholder="如 2026-06-30">
        <label>地区</label>
        <input type="text" id="mRegion">
        <label>招标类型</label>
        <select id="mBidType">
            <option value="">未知</option>
            <option value="公开招标">公开招标</option>
            <option value="邀请招标">邀请招标</option>
            <option value="竞争性谈判">竞争性谈判</option>
            <option value="竞争性磋商">竞争性磋商</option>
            <option value="询价采购">询价采购</option>
            <option value="单一来源">单一来源</option>
            <option value="比选">比选</option>
            <option value="中标公示">中标公示</option>
        </select>
        <label>联系方式</label>
        <input type="text" id="mContact">
        <label>发布日期</label>
        <input type="date" id="mDate">
        <div class="modal-actions">
            <button class="btn btn-outline" onclick="closeModal()">取消</button>
            <button class="btn btn-primary" onclick="saveArticle()">保存</button>
        </div>
    </div>
</div>

<script>
let currentPage = 1;

// Check auth on load
fetch('/api/check-auth').then(r=>r.json()).then(d=>{
    if(d.logged_in) showDashboard();
});

function doLogin() {
    const u = document.getElementById('username').value;
    const p = document.getElementById('password').value;
    fetch('/api/login', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({username:u, password:p})})
    .then(r => { if(r.ok) { showDashboard(); } else { document.getElementById('loginError').style.display='block'; } });
}

function doLogout() {
    fetch('/api/logout', {method:'POST'}).then(()=>{ document.getElementById('dashboard').style.display='none'; document.getElementById('loginPage').style.display='flex'; });
}

function showDashboard() {
    document.getElementById('loginPage').style.display='none';
    document.getElementById('dashboard').style.display='block';
    loadStats();
    loadArticles();
    loadKeywords();
    loadApis();
    pollStatus();
}

// Stats
function loadStats() {
    fetch('/api/stats').then(r=>r.json()).then(d=>{
        document.getElementById('statTotal').textContent = d.total;
        document.getElementById('statValid').textContent = d.valid_links;
        document.getElementById('statInvalid').textContent = d.invalid_links;
        document.getElementById('statManual').textContent = d.manual_count;
    });
}

// Articles
function loadArticles() {
    const cat = document.getElementById('filterCategory').value;
    const kw = document.getElementById('filterKeyword').value;
    fetch(`/api/articles?category=${cat}&keyword=${kw}&page=${currentPage}&per_page=30`)
    .then(r=>r.json()).then(d=>{
        const tbody = document.getElementById('articlesBody');
        tbody.innerHTML = d.articles.map(a => {
            const tagClass = {'招标采购':'tag-bid','材料采购':'tag-material','窑炉维修':'tag-furnace'}[a.category]||'tag-bid';
            let linkIcon = '<span class="link-unknown">？</span>';
            if(a.link_valid===1) linkIcon = '<span class="link-ok">✓</span>';
            else if(a.link_valid===0) linkIcon = '<span class="link-bad">✗</span>';
            // 生成可点击URL：有效http链接直接用，百度token等走/go代理
            let clickUrl = escHtml(a.url);
            if(a.url && !a.url.startsWith('http://') && !a.url.startsWith('https://')) {
                clickUrl = '/go?url=' + encodeURIComponent(a.url) + '&id=' + a.id;
            } else if(a.url && (a.url.includes('baidu.com/link') || a.url.includes('baidu.com/baidu.php'))) {
                clickUrl = '/go?url=' + encodeURIComponent(a.url) + '&id=' + a.id;
            }
            return `<tr>
                <td class="title-cell"><a href="${clickUrl}" target="_blank">${escHtml(a.title)}</a>
                    ${a.budget?'<br><small style="color:var(--orange)">💰'+escHtml(a.budget)+'</small>':''}
                    ${a.deadline?'<small style="color:var(--pink)"> ⏰'+escHtml(a.deadline)+'</small>':''}
                    ${a.publisher?'<br><small style="color:var(--text3)">🏢'+escHtml(a.publisher)+'</small>':''}
                </td>
                <td>${escHtml(a.date||'-')}</td>
                <td><span class="tag ${tagClass}">${escHtml(a.category)}</span></td>
                <td>${escHtml(a.source)}</td>
                <td>${linkIcon}</td>
                <td>
                    <button class="btn btn-outline btn-sm" onclick="editArticle(${a.id})">编辑</button>
                    <button class="btn btn-danger btn-sm" onclick="deleteArticle(${a.id})">删除</button>
                </td>
            </tr>`;
        }).join('');

        // Pagination
        const pg = document.getElementById('pagination');
        let phtml = '';
        for(let i=1;i<=d.pages;i++) {
            phtml += `<button class="${i===d.page?'active':''}" onclick="currentPage=${i};loadArticles()">${i}</button>`;
        }
        pg.innerHTML = phtml;
    });
}

function editArticle(id) {
    fetch(`/api/articles?per_page=1000`).then(r=>r.json()).then(d=>{
        const a = d.articles.find(x=>x.id===id);
        if(!a) return;
        document.getElementById('modalTitle').textContent = '编辑资讯';
        document.getElementById('editId').value = id;
        document.getElementById('mTitle').value = a.title||'';
        document.getElementById('mUrl').value = a.url||'';
        document.getElementById('mCategory').value = a.category||'招标采购';
        document.getElementById('mSnippet').value = a.snippet||'';
        document.getElementById('mPublisher').value = a.publisher||'';
        document.getElementById('mBudget').value = a.budget||'';
        document.getElementById('mDeadline').value = a.deadline||'';
        document.getElementById('mRegion').value = a.region||'';
        document.getElementById('mBidType').value = a.bid_type||'';
        document.getElementById('mContact').value = a.contact||'';
        document.getElementById('mDate').value = a.date||'';
        document.getElementById('articleModal').classList.add('show');
    });
}

function deleteArticle(id) {
    if(!confirm('确定删除这条资讯？')) return;
    fetch(`/api/articles/${id}`, {method:'DELETE'}).then(()=>{ loadArticles(); loadStats(); });
}

function showAddModal() {
    document.getElementById('modalTitle').textContent = '添加资讯';
    document.getElementById('editId').value = '';
    ['mTitle','mUrl','mSnippet','mPublisher','mBudget','mDeadline','mRegion','mContact'].forEach(id=>document.getElementById(id).value='');
    document.getElementById('mCategory').value='招标采购';
    document.getElementById('mBidType').value='';
    document.getElementById('mDate').value=new Date().toISOString().slice(0,10);
    document.getElementById('articleModal').classList.add('show');
}

function closeModal() {
    document.getElementById('articleModal').classList.remove('show');
}

function saveArticle() {
    const id = document.getElementById('editId').value;
    const data = {
        title: document.getElementById('mTitle').value,
        url: document.getElementById('mUrl').value,
        category: document.getElementById('mCategory').value,
        snippet: document.getElementById('mSnippet').value,
        publisher: document.getElementById('mPublisher').value,
        budget: document.getElementById('mBudget').value,
        deadline: document.getElementById('mDeadline').value,
        region: document.getElementById('mRegion').value,
        bid_type: document.getElementById('mBidType').value,
        contact: document.getElementById('mContact').value,
        date: document.getElementById('mDate').value,
    };

    if(id) {
        fetch(`/api/articles/${id}`, {method:'PUT', headers:{'Content-Type':'application/json'}, body:JSON.stringify(data)});
    } else {
        fetch('/api/articles', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(data)});
    }
    closeModal();
    setTimeout(()=>{ loadArticles(); loadStats(); }, 500);
}

// Update
function triggerUpdate() {
    document.getElementById('updateBtn').disabled = true;
    fetch('/api/update', {method:'POST'}).then(r=>r.json()).then(d=>{
        if(d.error) alert(d.error);
        else pollStatus();
    });
}

function validateLinks() {
    fetch('/api/validate-links', {method:'POST'});
    alert('链接验证已在后台启动，请稍后刷新查看结果');
}

function pollStatus() {
    fetch('/api/status').then(r=>r.json()).then(d=>{
        const dot = document.getElementById('statusDot');
        const text = document.getElementById('statusText');
        const btn = document.getElementById('updateBtn');
        if(d.running) {
            dot.className = 'status-dot running';
            text.textContent = d.progress;
            btn.disabled = true;
            setTimeout(pollStatus, 3000);
        } else {
            dot.className = 'status-dot idle';
            text.textContent = '就绪';
            btn.disabled = false;
            if(d.last_update) {
                document.getElementById('lastUpdateTime').textContent = '上次更新: ' + d.last_update;
            }
            if(d.result_count > 0) {
                loadArticles();
                loadStats();
            }
        }
    });
}

// Keywords
function loadKeywords() {
    fetch('/api/keywords').then(r=>r.json()).then(d=>{
        const list = document.getElementById('keywordsList');
        list.innerHTML = d.keywords.map((kw,i) =>
            `<span class="kw-chip">${escHtml(kw)} <span class="remove" onclick="removeKeyword(${i})">×</span></span>`
        ).join('');
    });
}

function addKeyword() {
    const input = document.getElementById('newKeyword');
    const kw = input.value.trim();
    if(!kw) return;
    fetch('/api/keywords').then(r=>r.json()).then(d=>{
        d.keywords.push(kw);
        fetch('/api/keywords', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({keywords:d.keywords})})
        .then(()=>{ input.value=''; loadKeywords(); });
    });
}

function removeKeyword(idx) {
    fetch('/api/keywords').then(r=>r.json()).then(d=>{
        d.keywords.splice(idx,1);
        fetch('/api/keywords', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({keywords:d.keywords})})
        .then(()=>loadKeywords());
    });
}

// APIs
function loadApis() {
    fetch('/api/api-sources').then(r=>r.json()).then(d=>{
        const list = document.getElementById('apisList');
        list.innerHTML = Object.entries(d.sources).map(([key,s]) => `
            <div style="background:var(--card);border-radius:var(--radius);padding:16px 20px;margin-bottom:8px;box-shadow:var(--shadow);display:flex;align-items:center;gap:12px;">
                <div style="flex:1;">
                    <strong>${escHtml(s.name||key)}</strong>
                    <span style="color:${s.enabled?'var(--green)':'var(--text3)'};font-size:0.82rem;margin-left:8px;">${s.enabled?'已启用':'未启用'}</span>
                    <br><small style="color:var(--text3)">${escHtml(s.api_url||'')} · ${s.api_type||'html'}</small>
                </div>
                <button class="btn btn-sm ${s.enabled?'btn-outline':'btn-success'}" onclick="toggleApi('${key}',${!s.enabled})">${s.enabled?'禁用':'启用'}</button>
                <button class="btn btn-danger btn-sm" onclick="deleteApi('${key}')">删除</button>
            </div>
        `).join('');
    });
}

function toggleApi(key, enabled) {
    fetch(`/api/api-sources/${key}/toggle`, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({enabled})})
    .then(()=>loadApis());
}

function deleteApi(key) {
    if(!confirm('确定删除？')) return;
    fetch(`/api/api-sources/${key}`, {method:'DELETE'}).then(()=>loadApis());
}

// Tab switch
function switchAdminTab(name) {
    document.querySelectorAll('.tab-content').forEach(t=>t.classList.remove('active'));
    document.querySelectorAll('.tab-nav button').forEach(b=>b.classList.remove('active'));
    document.getElementById('tab-'+name).classList.add('active');
    event.currentTarget.classList.add('active');
}

function escHtml(s) { if(!s) return ''; return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }

// Enter key login
document.getElementById('password').addEventListener('keydown', e=>{ if(e.key==='Enter') doLogin(); });
</script>
</body>
</html>
"""


# ==================== 启动 ====================

def start_server(host=None, port=None, debug=None):
    host = host or config.FLASK_HOST
    port = port or config.FLASK_PORT
    debug = debug if debug is not None else config.FLASK_DEBUG

    init_db()
    logger.info(f"🌐 启动服务器: http://{host}:{port}")
    logger.info(f"📋 后台管理: http://{host}:{port}/admin")
    app.run(host=host, port=port, debug=debug, use_reloader=False)


if __name__ == "__main__":
    start_server()
