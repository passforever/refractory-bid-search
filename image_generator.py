"""
耐火材料招标采购信息搜索工具 - 今日摘要图片生成器 v3.1
生成精美的每日摘要卡片图片，可分享到微信群
"""

import os
import sys
import sqlite3
from datetime import datetime, timedelta
from io import BytesIO

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from PIL import Image, ImageDraw, ImageFont

import config


def _get_app_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


# ==================== 字体配置 ====================

def _load_fonts():
    """加载中文字体"""
    font_dir = "C:/Windows/Fonts"

    # 优先使用微软雅黑
    font_paths = {
        'regular': os.path.join(font_dir, 'msyh.ttc'),
        'bold': os.path.join(font_dir, 'msyhbd.ttc'),
        'black': os.path.join(font_dir, 'simhei.ttf'),
    }

    fonts = {}
    for name, path in font_paths.items():
        if os.path.exists(path):
            fonts[name] = path

    # fallback
    if 'regular' not in fonts:
        fonts['regular'] = os.path.join(font_dir, 'simsun.ttc')
    if 'bold' not in fonts:
        fonts['bold'] = fonts.get('regular', os.path.join(font_dir, 'simsun.ttc'))

    return fonts


# ==================== 颜色主题 ====================

COLORS = {
    'bg_gradient_top': (20, 30, 70),       # 深蓝渐变顶部
    'bg_gradient_bottom': (40, 60, 120),    # 深蓝渐变底部
    'card_bg': (255, 255, 255, 240),        # 白色卡片背景（半透明）
    'accent_blue': (0, 113, 227),           # 苹果蓝
    'accent_green': (52, 199, 89),          # 苹果绿
    'accent_orange': (255, 149, 0),         # 苹果橙
    'accent_pink': (255, 45, 85),           # 苹果粉
    'text_primary': (29, 29, 31),           # 主文字色
    'text_secondary': (110, 110, 115),      # 副文字色
    'text_white': (255, 255, 255),          # 白色文字
    'divider': (210, 210, 215),             # 分割线
    'stat_bg': (245, 245, 247),             # 统计背景
    'highlight': (0, 113, 227),             # 高亮色
}


def _get_today_stats():
    """从数据库获取今日统计"""
    db_path = os.path.join(_get_app_dir(), config.DB_NAME)
    db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row

    cutoff = (datetime.now() - timedelta(days=config.MAX_DAYS_OLD)).strftime("%Y-%m-%d")
    today = datetime.now().strftime("%Y-%m-%d")

    # 总数和分类
    total = db.execute(
        "SELECT COUNT(*) FROM articles WHERE is_deleted=0 AND date >= ?",
        (cutoff,)
    ).fetchone()[0]

    # 今日新增
    today_count = db.execute(
        "SELECT COUNT(*) FROM articles WHERE is_deleted=0 AND date = ?",
        (today,)
    ).fetchone()[0]

    # 分类统计
    categories = db.execute("""
        SELECT category, COUNT(*) as cnt FROM articles
        WHERE is_deleted=0 AND date >= ?
        GROUP BY category ORDER BY cnt DESC
    """, (cutoff,)).fetchall()

    # 各分类top3条目
    top_items = {}
    for cat in categories:
        cat_name = cat['category']
        rows = db.execute("""
            SELECT title, budget, deadline, region, publisher FROM articles
            WHERE is_deleted=0 AND date >= ? AND category = ?
            ORDER BY relevance_score DESC LIMIT 5
        """, (cutoff, cat_name)).fetchall()
        top_items[cat_name] = [dict(r) for r in rows]

    # 有效链接数
    valid_count = db.execute(
        "SELECT COUNT(*) FROM articles WHERE is_deleted=0 AND date >= ? AND (link_valid IS NULL OR link_valid = 1)",
        (cutoff,)
    ).fetchone()[0]

    db.close()

    return {
        'total': total,
        'today_count': today_count,
        'categories': {r['category']: r['cnt'] for r in categories},
        'top_items': top_items,
        'valid_count': valid_count,
        'date': today,
        'update_time': datetime.now().strftime("%Y-%m-%d %H:%M"),
    }


def generate_summary_image(output_path=None):
    """生成今日摘要卡片图片

    Args:
        output_path: 输出路径，None则返回BytesIO

    Returns:
        如果output_path为None，返回BytesIO；否则返回文件路径
    """
    fonts = _load_fonts()
    stats = _get_today_stats()

    # 图片尺寸（适合微信分享：宽 800px）
    W, H = 800, 1200
    img = Image.new('RGBA', (W, H), COLORS['bg_gradient_top'])
    draw = ImageDraw.Draw(img)

    # ==================== 绘制渐变背景 ====================
    for y in range(H):
        ratio = y / H
        r = int(COLORS['bg_gradient_top'][0] * (1 - ratio) + COLORS['bg_gradient_bottom'][0] * ratio)
        g = int(COLORS['bg_gradient_top'][1] * (1 - ratio) + COLORS['bg_gradient_bottom'][1] * ratio)
        b = int(COLORS['bg_gradient_top'][2] * (1 - ratio) + COLORS['bg_gradient_bottom'][2] * ratio)
        draw.line([(0, y), (W, y)], fill=(r, g, b))

    # ==================== 装饰元素 ====================
    # 顶部半透明圆形装饰
    overlay = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    overlay_draw.ellipse([550, -80, 900, 270], fill=(255, 255, 255, 12))
    overlay_draw.ellipse([-100, 900, 250, 1250], fill=(255, 255, 255, 8))
    img = Image.alpha_composite(img, overlay)
    draw = ImageDraw.Draw(img)

    # ==================== 标题区域 ====================
    font_title = ImageFont.truetype(fonts['bold'], 36)
    font_subtitle = ImageFont.truetype(fonts['regular'], 20)
    font_date = ImageFont.truetype(fonts['regular'], 18)

    y = 40

    # 标题
    draw.text((50, y), "耐火材料招标日报", fill=COLORS['text_white'], font=font_title)
    y += 50

    # 日期 & 更新时间
    date_str = stats['date']
    weekday = ['周一', '周二', '周三', '周四', '周五', '周六', '周日'][datetime.now().weekday()]
    draw.text((50, y), f"{date_str}  {weekday}", fill=(200, 210, 230), font=font_date)
    y += 28
    draw.text((50, y), f"更新时间: {stats['update_time']}", fill=(160, 170, 200), font=font_date)
    y += 50

    # ==================== 统计卡片区域 ====================
    card_y = y
    card_h = 100
    card_margin = 15
    card_w = (W - 100 - card_margin * 3) // 4

    stat_items = [
        ("总量", str(stats['total']), COLORS['accent_blue']),
        ("今日新增", str(stats['today_count']), COLORS['accent_green']),
        ("有效链接", str(stats['valid_count']), COLORS['accent_orange']),
        ("分类数", str(len(stats['categories'])), COLORS['accent_pink']),
    ]

    for i, (label, value, color) in enumerate(stat_items):
        x = 50 + i * (card_w + card_margin)

        # 卡片背景（圆角矩形）
        card_img = Image.new('RGBA', (card_w, card_h), (0, 0, 0, 0))
        card_draw = ImageDraw.Draw(card_img)
        card_draw.rounded_rectangle([(0, 0), (card_w, card_h)], radius=12, fill=(255, 255, 255, 25))
        img.paste(Image.alpha_composite(
            Image.new('RGBA', (card_w, card_h), (0, 0, 0, 0)),
            card_img
        ), (x, card_y))
        draw = ImageDraw.Draw(img)

        # 数字
        font_num = ImageFont.truetype(fonts['bold'], 32)
        draw.text((x + 16, card_y + 12), value, fill=color, font=font_num)
        # 标签
        font_label = ImageFont.truetype(fonts['regular'], 15)
        draw.text((x + 16, card_y + 60), label, fill=(180, 190, 210), font=font_label)

    y = card_y + card_h + 30

    # ==================== 分类统计 ====================
    font_section = ImageFont.truetype(fonts['bold'], 22)
    font_cat_label = ImageFont.truetype(fonts['regular'], 17)
    font_cat_num = ImageFont.truetype(fonts['bold'], 17)

    draw.text((50, y), "📊 分类概览", fill=COLORS['text_white'], font=font_section)
    y += 38

    cat_colors = {
        '招标采购': COLORS['accent_blue'],
        '材料采购': COLORS['accent_green'],
        '窑炉维修': COLORS['accent_pink'],
    }

    for cat_name, cnt in stats['categories'].items():
        color = cat_colors.get(cat_name, COLORS['accent_orange'])
        bar_max_w = W - 220

        # 分类名
        draw.text((50, y), cat_name, fill=(200, 210, 230), font=font_cat_label)
        # 数字
        num_text = f"{cnt}条"
        draw.text((170, y), num_text, fill=color, font=font_cat_num)
        # 进度条背景
        bar_y = y + 26
        draw.rounded_rectangle([(50, bar_y), (50 + bar_max_w, bar_y + 8)], radius=4, fill=(255, 255, 255, 30))
        # 进度条
        bar_ratio = min(cnt / max(stats['total'], 1), 1.0)
        bar_w = max(int(bar_max_w * bar_ratio), 4)
        draw.rounded_rectangle([(50, bar_y), (50 + bar_w, bar_y + 8)], radius=4, fill=(*color, 220))
        y += 48

    y += 10

    # ==================== 热门条目区域 ====================
    draw.text((50, y), "🔥 热门招标", fill=COLORS['text_white'], font=font_section)
    y += 40

    font_item_title = ImageFont.truetype(fonts['bold'], 17)
    font_item_detail = ImageFont.truetype(fonts['regular'], 14)

    # 创建白色内容区域
    content_h = H - y - 80
    content_img = Image.new('RGBA', (W - 100, content_h), (0, 0, 0, 0))
    content_draw = ImageDraw.Draw(content_img)
    content_draw.rounded_rectangle(
        [(0, 0), (W - 100, content_h)],
        radius=16, fill=(255, 255, 255, 245)
    )
    img.paste(Image.alpha_composite(
        Image.new('RGBA', (W - 100, content_h), (0, 0, 0, 0)),
        content_img
    ), (50, y))

    # 在白色区域上绘制条目
    item_y = y + 16

    displayed = 0
    for cat_name, items in stats['top_items'].items():
        if not items:
            continue

        # 分类标签
        cat_color = cat_colors.get(cat_name, COLORS['accent_orange'])
        tag_img = Image.new('RGBA', (120, 26), (0, 0, 0, 0))
        tag_draw = ImageDraw.Draw(tag_img)
        tag_draw.rounded_rectangle([(0, 0), (120, 26)], radius=13,
                                   fill=(*cat_color, 30))
        img.paste(Image.alpha_composite(
            Image.new('RGBA', (120, 26), (0, 0, 0, 0)),
            tag_img
        ), (66, item_y))
        draw = ImageDraw.Draw(img)

        font_tag = ImageFont.truetype(fonts['bold'], 13)
        draw.text((66 + 12, item_y + 4), cat_name, fill=cat_color, font=font_tag)
        item_y += 34

        for idx, item in enumerate(items[:3]):
            if displayed >= 9:  # 最多显示9条
                break

            # 序号
            num_str = f"{idx + 1}"
            num_img = Image.new('RGBA', (24, 24), (0, 0, 0, 0))
            num_draw = ImageDraw.Draw(num_img)
            num_draw.ellipse([(0, 0), (24, 24)], fill=(*cat_color, 200))
            img.paste(Image.alpha_composite(
                Image.new('RGBA', (24, 24), (0, 0, 0, 0)),
                num_img
            ), (70, item_y + 2))
            draw = ImageDraw.Draw(img)

            font_num_small = ImageFont.truetype(fonts['bold'], 12)
            # 居中数字
            bbox = draw.textbbox((0, 0), num_str, font=font_num_small)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
            draw.text((70 + (24 - tw) // 2, item_y + 2 + (24 - th) // 2),
                      num_str, fill=COLORS['text_white'], font=font_num_small)

            # 标题（截断）
            title = item['title']
            if len(title) > 32:
                title = title[:30] + "..."
            draw.text((102, item_y + 3), title, fill=COLORS['text_primary'], font=font_item_title)

            # 详细信息行
            detail_parts = []
            if item.get('budget'):
                detail_parts.append(f"💰 {item['budget']}")
            if item.get('deadline'):
                detail_parts.append(f"⏰ {item['deadline']}")
            if item.get('region'):
                detail_parts.append(f"📍 {item['region']}")
            if item.get('publisher'):
                detail_parts.append(f"🏢 {item['publisher']}")

            if detail_parts:
                detail_text = "  ".join(detail_parts[:3])
                if len(detail_text) > 50:
                    detail_text = detail_text[:48] + "..."
                draw.text((102, item_y + 26), detail_text,
                          fill=COLORS['text_secondary'], font=font_item_detail)

            item_y += 52
            displayed += 1

        if displayed >= 9:
            break

        # 分割线
        draw.line([(66, item_y - 6), (W - 66, item_y - 6)], fill=COLORS['divider'], width=1)
        item_y += 6

    # ==================== 底部信息 ====================
    font_footer = ImageFont.truetype(fonts['regular'], 14)
    footer_y = H - 60
    draw.text((50, footer_y), "耐火材料招标搜索工具 · 每日自动更新",
              fill=(140, 150, 180), font=font_footer)
    draw.text((50, footer_y + 22), "数据来源：百度搜索 / Bing / 招标网站",
              fill=(120, 130, 160), font=font_footer)

    # ==================== 输出 ====================
    # 转为RGB（去掉alpha通道）
    img_rgb = Image.new('RGB', img.size, COLORS['bg_gradient_top'])
    img_rgb.paste(img, mask=img.split()[3])

    if output_path:
        img_rgb.save(output_path, 'PNG', quality=95)
        return output_path
    else:
        buf = BytesIO()
        img_rgb.save(buf, 'PNG', quality=95)
        buf.seek(0)
        return buf


if __name__ == "__main__":
    path = os.path.join(_get_app_dir(), "reports", "今日摘要.png")
    result = generate_summary_image(path)
    print(f"摘要图片已生成: {result}")
