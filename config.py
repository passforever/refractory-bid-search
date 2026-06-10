"""
耐火材料招标采购信息搜索工具 - 配置文件 v3.0
支持关键词管理、API数据源配置、后台管理、时效过滤
"""

import json
import os
import sys

def _get_app_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

# ==================== 搜索关键词配置 ====================

BID_KEYWORDS = [
    "耐火材料 招标",
    "耐火材料 采购",
    "耐火材料 竞标",
    "耐火材料 比价",
    "耐火材料 竞争性谈判",
]

FURNACE_KEYWORDS = [
    "高炉 维修 招标",
    "高炉 耐火材料",
    "热风炉 维修 招标",
    "热风炉 耐火材料",
    "焦炉 维修 招标",
    "焦炉 耐火材料",
    "窑炉 维修 招标",
    "加热炉 耐火材料",
    "回转窑 耐火材料",
    "锅炉 耐火浇注料",
]

MATERIAL_KEYWORDS = [
    "高铝砖 招标",
    "高铝砖 采购",
    "粘土砖 招标",
    "粘土砖 采购",
    "轻质砖 招标",
    "轻质保温砖 采购",
    "硅砖 招标",
    "硅砖 采购",
    "不定型耐火材料 招标",
    "不定型材料 采购",
    "耐火浇注料 招标",
    "耐火浇注料 采购",
    "散料 招标 耐火",
    "耐火泥浆 招标",
    "耐火泥浆 采购",
    "耐火喷涂料 招标",
    "耐火可塑料 采购",
]

ALL_KEYWORDS = BID_KEYWORDS + FURNACE_KEYWORDS + MATERIAL_KEYWORDS

# ==================== 搜索源配置 ====================

SEARCH_SOURCES = {
    "baidu": {
        "name": "百度搜索",
        "enabled": True,
        "base_url": "https://www.baidu.com/s",
        "max_pages": 3,
    },
    "bing": {
        "name": "必应搜索",
        "enabled": True,
        "base_url": "https://cn.bing.com/search",
        "max_pages": 2,
    },
    "chinabidding": {
        "name": "中国采购与招标网",
        "enabled": True,
        "base_url": "https://search.chinabidding.cn/search",
        "max_pages": 2,
    },
    "zhaobiao": {
        "name": "招标网",
        "enabled": True,
        "base_url": "https://www.zhaobiao.cn/search",
        "max_pages": 2,
    },
}

# ==================== 固定网站 API 数据源 ====================

API_SOURCES = {
    "ccgp": {
        "name": "中国政府采购网",
        "enabled": False,
        "api_url": "https://search.ccgp.gov.cn/bxsearch",
        "api_type": "html",
        "params": {
            "search_type": "1",
            "bidSort": "0",
            "buyerName": "",
            "projectId": "",
            "pinMu": "0",
            "bidType": "0",
            "dbselect": "bidx",
            "kw": "{keyword}",
            "start_time": "{date_30d_ago}",
            "end_time": "{today}",
            "timeType": "6",
        },
        "encoding": "utf-8",
        "result_selector": {
            "container": "div.vT-s",
            "title": "a",
            "url": "a[href]",
            "snippet": "p",
            "date": "span",
        },
    },
    "cebpubservice": {
        "name": "招标投标公共服务平台",
        "enabled": False,
        "api_url": "https://www.cebpubservice.com/search",
        "api_type": "html",
        "params": {
            "keyword": "{keyword}",
        },
        "encoding": "utf-8",
        "result_selector": {
            "container": "div.search-result-item",
            "title": "h3 a",
            "url": "h3 a[href]",
            "snippet": "p.result-desc",
            "date": "span.date",
        },
    },
}

# ==================== 过滤配置 ====================

MAX_DAYS_OLD = 30  # 只保留1个月内的资讯

EXCLUDE_KEYWORDS = [
    "求职", "招聘", "人才", "简历",
    "论文", "文献", "专利",
    "二手", "转让", "出售",
    "培训", "课程", "学习",
]

MUST_CONTAIN_ANY = [
    "耐火", "招标", "采购", "竞标", "中标", "比价",
    "高铝砖", "粘土砖", "轻质砖", "硅砖",
    "浇注料", "不定型", "泥浆", "散料",
    "高炉", "热风炉", "焦炉", "窑炉", "加热炉", "回转窑",
]

# ==================== 请求配置 ====================

REQUEST_DELAY_MIN = 2
REQUEST_DELAY_MAX = 5
REQUEST_TIMEOUT = 15
MAX_RETRIES = 2

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
}

# ==================== 输出配置 ====================

REPORT_DIR = "reports"
REPORT_FILENAME_FORMAT = "耐火材料招标_{date}.html"
DATE_FORMAT = "%Y-%m-%d"

# ==================== 后台管理配置 ====================

# 管理员账户（登录凭证不显示在网页上）
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "Refr@2026!Bid"

# Flask 服务器配置
FLASK_HOST = "127.0.0.1"
FLASK_PORT = 8899
FLASK_DEBUG = False

# 数据库
DB_NAME = "bid_data.db"

# 链接验证
LINK_VALIDATE_TIMEOUT = 8   # 链接验证超时秒数
LINK_VALIDATE_CONCURRENT = 5  # 并发验证数


# ==================== 配置管理器 ====================

class ConfigManager:
    """关键词与 API 配置管理器"""

    CUSTOM_CONFIG_FILE = "custom_config.json"

    @classmethod
    def get_config_path(cls):
        return os.path.join(_get_app_dir(), cls.CUSTOM_CONFIG_FILE)

    @classmethod
    def load_custom(cls):
        path = cls.get_config_path()
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    @classmethod
    def save_custom(cls, data: dict):
        path = cls.get_config_path()
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    @classmethod
    def get_keywords(cls):
        custom = cls.load_custom()
        if "keywords" in custom:
            return custom["keywords"]
        return ALL_KEYWORDS

    @classmethod
    def set_keywords(cls, keywords: list):
        custom = cls.load_custom()
        custom["keywords"] = keywords
        cls.save_custom(custom)

    @classmethod
    def get_api_sources(cls):
        custom = cls.load_custom()
        sources = dict(API_SOURCES)
        if "api_sources" in custom:
            sources.update(custom["api_sources"])
        return sources

    @classmethod
    def add_api_source(cls, key: str, config: dict):
        custom = cls.load_custom()
        if "api_sources" not in custom:
            custom["api_sources"] = {}
        custom["api_sources"][key] = config
        cls.save_custom(custom)

    @classmethod
    def remove_api_source(cls, key: str):
        custom = cls.load_custom()
        if "api_sources" in custom and key in custom["api_sources"]:
            del custom["api_sources"][key]
            cls.save_custom(custom)

    @classmethod
    def toggle_api_source(cls, key: str, enabled: bool):
        custom = cls.load_custom()
        if "api_sources" not in custom:
            custom["api_sources"] = {}
        if key not in custom["api_sources"]:
            custom["api_sources"][key] = dict(API_SOURCES.get(key, {}))
        custom["api_sources"][key]["enabled"] = enabled
        cls.save_custom(custom)
