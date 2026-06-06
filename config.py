"""
耐火材料招标采购信息搜索工具 - 配置文件
"""

# ==================== 搜索关键词配置 ====================

# 主关键词：招标/采购类
BID_KEYWORDS = [
    "耐火材料 招标",
    "耐火材料 采购",
    "耐火材料 竞标",
    "耐火材料 比价",
    "耐火材料 竞争性谈判",
]

# 窑炉类关键词
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

# 材料类关键词
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

# 所有关键词合集
ALL_KEYWORDS = BID_KEYWORDS + FURNACE_KEYWORDS + MATERIAL_KEYWORDS

# ==================== 搜索源配置 ====================

SEARCH_SOURCES = {
    "baidu": {
        "name": "百度搜索",
        "enabled": True,
        "base_url": "https://www.baidu.com/s",
        "max_pages": 3,  # 每个关键词搜索的最大页数
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

# ==================== 过滤配置 ====================

# 结果日期过滤：只保留最近 N 天内的结果
MAX_DAYS_OLD = 30

# 排除的关键词（标题/摘要中包含这些词则过滤掉）
EXCLUDE_KEYWORDS = [
    "求职", "招聘", "人才", "简历",
    "论文", "文献", "专利",
    "二手", "转让", "出售",
    "培训", "课程", "学习",
]

# 必须包含至少一个核心词（避免搜索结果偏离主题）
MUST_CONTAIN_ANY = [
    "耐火", "招标", "采购", "竞标", "中标", "比价",
    "高铝砖", "粘土砖", "轻质砖", "硅砖",
    "浇注料", "不定型", "泥浆", "散料",
    "高炉", "热风炉", "焦炉", "窑炉", "加热炉", "回转窑",
]

# ==================== 请求配置 ====================

# 请求间隔（秒），避免被反爬
REQUEST_DELAY_MIN = 2
REQUEST_DELAY_MAX = 5

# 请求超时（秒）
REQUEST_TIMEOUT = 15

# 最大重试次数
MAX_RETRIES = 2

# 请求头
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
}

# ==================== 输出配置 ====================

# 报告输出目录
REPORT_DIR = "reports"

# 报告文件名格式
REPORT_FILENAME_FORMAT = "耐火材料招标_{date}.html"

# 日期格式
DATE_FORMAT = "%Y-%m-%d"
