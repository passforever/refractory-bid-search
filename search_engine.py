"""
耐火材料招标采购信息搜索工具 - 核心搜索引擎
支持多源搜索、关键词组合、日期过滤、结果去重
"""

import re
import sys
import os
import time
import random
import hashlib
import logging
from datetime import datetime, timedelta
from urllib.parse import quote, urljoin, urlparse, parse_qs
from typing import List, Dict, Optional, Set
from dataclasses import dataclass, field

# 修复 Windows 终端 UTF-8 编码
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# 添加应用程序目录到路径（兼容 PyInstaller 打包）
def _get_app_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

sys.path.insert(0, _get_app_dir())

import requests
from bs4 import BeautifulSoup

import config

# ==================== 日志配置 ====================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ==================== 数据模型 ====================

@dataclass
class SearchResult:
    """单条搜索结果"""
    title: str = ""
    url: str = ""
    snippet: str = ""
    source: str = ""       # 来源平台（百度、必应等）
    keyword: str = ""      # 匹配的关键词
    date: str = ""         # 发布日期
    category: str = ""     # 分类（招标/窑炉维修/材料采购）
    relevance_score: float = 0.0  # 相关度评分

    @property
    def uid(self) -> str:
        """唯一标识，用于去重"""
        # 用 URL 的域名+路径（去掉查询参数）作为唯一标识
        parsed = urlparse(self.url)
        key = f"{parsed.netloc}{parsed.path}"
        return hashlib.md5(key.encode()).hexdigest()


@dataclass
class SearchReport:
    """搜索报告"""
    search_time: str = ""
    total_keywords: int = 0
    total_searched: int = 0
    total_results: int = 0
    results: List[SearchResult] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    source_stats: Dict[str, int] = field(default_factory=dict)
    category_stats: Dict[str, int] = field(default_factory=dict)


# ==================== 搜索引擎基类 ====================

class BaseSearchEngine:
    """搜索引擎基类"""

    def __init__(self, name: str, base_url: str):
        self.name = name
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update(config.HEADERS)

    def _delay(self):
        """随机延迟，避免反爬"""
        delay = random.uniform(config.REQUEST_DELAY_MIN, config.REQUEST_DELAY_MAX)
        time.sleep(delay)

    def _fetch_page(self, url: str, encoding: str = "utf-8") -> Optional[str]:
        """获取页面内容"""
        for attempt in range(config.MAX_RETRIES + 1):
            try:
                resp = self.session.get(url, timeout=config.REQUEST_TIMEOUT)
                resp.encoding = encoding
                if resp.status_code == 200:
                    return resp.text
                logger.warning(f"[{self.name}] HTTP {resp.status_code} for {url}")
            except requests.RequestException as e:
                logger.warning(f"[{self.name}] 请求失败 (尝试 {attempt+1}/{config.MAX_RETRIES+1}): {e}")
                if attempt < config.MAX_RETRIES:
                    time.sleep(3)
        return None

    def search(self, keyword: str, max_pages: int = 2) -> List[SearchResult]:
        """搜索关键词，返回结果列表"""
        raise NotImplementedError

    def _classify_result(self, result: SearchResult) -> str:
        """对结果进行分类"""
        text = (result.title + " " + result.snippet).lower()
        if any(k in text for k in ["维修", "检修", "砌筑", "施工", "筑炉"]):
            return "窑炉维修"
        if any(k in text for k in ["高铝砖", "粘土砖", "轻质砖", "硅砖", "浇注料", "不定型", "泥浆", "散料", "可塑料", "喷涂料"]):
            return "材料采购"
        return "招标采购"

    def _calculate_relevance(self, result: SearchResult) -> float:
        """计算相关度评分"""
        score = 50.0  # 基础分
        text = (result.title + " " + result.snippet).lower()

        # 关键词命中加分
        high_value = ["耐火", "招标", "采购", "中标", "高铝砖", "硅砖", "浇注料"]
        for kw in high_value:
            if kw in text:
                score += 10

        # 窑炉类型加分
        furnaces = ["高炉", "热风炉", "焦炉", "窑炉", "加热炉", "回转窑"]
        for kw in furnaces:
            if kw in text:
                score += 8

        # 时间加分（越新越高）
        if result.date:
            try:
                pub_date = datetime.strptime(result.date[:10], "%Y-%m-%d")
                days_ago = (datetime.now() - pub_date).days
                if days_ago <= 3:
                    score += 20
                elif days_ago <= 7:
                    score += 15
                elif days_ago <= 14:
                    score += 10
                elif days_ago <= 30:
                    score += 5
            except (ValueError, IndexError):
                pass

        # 排除词减分
        for ex in config.EXCLUDE_KEYWORDS:
            if ex in text:
                score -= 30

        return max(0, min(100, score))


# ==================== 百度搜索 ====================

class BaiduSearchEngine(BaseSearchEngine):
    """百度搜索引擎"""

    def __init__(self):
        super().__init__("百度", config.SEARCH_SOURCES["baidu"]["base_url"])

    def search(self, keyword: str, max_pages: int = 3) -> List[SearchResult]:
        results = []
        for page in range(max_pages):
            pn = page * 10
            url = f"{self.base_url}?wd={quote(keyword)}&pn={pn}&rn=10"
            logger.info(f"[百度] 搜索: {keyword} (第{page+1}页)")

            html = self._fetch_page(url)
            if not html:
                continue

            page_results = self._parse_baidu_results(html, keyword)
            results.extend(page_results)
            self._delay()

        return results

    def _parse_baidu_results(self, html: str, keyword: str) -> List[SearchResult]:
        results = []
        soup = BeautifulSoup(html, "html.parser")

        # 百度搜索结果容器 - 多种选择器兼容
        items = soup.select("div.result, div.c-container")
        if not items:
            items = soup.select("div[class*='result']")
        if not items:
            # 尝试更宽泛的选择器
            items = soup.select("#content_left > div")
        if not items:
            # 最终回退：找所有包含 h3 和 a 的 div
            items = [div for div in soup.find_all("div") if div.find("h3") and div.find("a")]

        for item in items:
            try:
                result = SearchResult(source=self.name, keyword=keyword)

                # 提取标题 - 多种选择器兼容
                title_tag = (
                    item.select_one("h3 a")
                    or item.select_one(".t a")
                    or item.select_one(".c-title a")
                    or item.select_one("a[href]")
                )
                if title_tag:
                    result.title = title_tag.get_text(strip=True)
                    href = title_tag.get("href", "")
                    if href:
                        result.url = href  # 先保存原始链接，后续统一解析

                # 提取摘要 - 多种选择器兼容
                snippet_tag = (
                    item.select_one(".c-abstract")
                    or item.select_one(".c-span-last")
                    or item.select_one(".content-right_8Zs40")
                    or item.select_one("span.content-right_8Zs40")
                    or item.select_one("[class*='abstract']")
                    or item.select_one("[class*='content-right']")
                )
                if snippet_tag:
                    result.snippet = snippet_tag.get_text(strip=True)
                elif result.title:
                    # 回退：获取所有文本，去除标题
                    all_text = item.get_text(separator=" ", strip=True)
                    snippet = all_text.replace(result.title, "", 1).strip()
                    # 清理片段（去掉过长文本）
                    if len(snippet) > 300:
                        snippet = snippet[:300] + "..."
                    result.snippet = snippet

                # 提取日期 - 增强匹配
                text_content = item.get_text()
                # 匹配各种日期格式
                date_patterns = [
                    r'(\d{4}[-/年]\d{1,2}[-/月]\d{1,2}[日]?)',  # 2024-01-15 / 2024年1月15日
                    r'(\d{1,2}[-/月]\d{1,2}[日]?\s*\d{4})',      # 1月15日 2024
                    r'(\d+天前|\d+小时前|\d+分钟前)',              # 3天前 / 2小时前
                ]
                for pattern in date_patterns:
                    date_match = re.search(pattern, text_content)
                    if date_match:
                        date_str = date_match.group(1)
                        date_str = date_str.replace("年", "-").replace("月", "-").replace("日", "").replace("/", "-")
                        # 处理相对日期
                        if "天前" in date_str:
                            days = int(re.search(r'(\d+)', date_str).group(1))
                            result.date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
                        elif "小时前" in date_str:
                            hours = int(re.search(r'(\d+)', date_str).group(1))
                            result.date = (datetime.now() - timedelta(hours=hours)).strftime("%Y-%m-%d")
                        elif "分钟前" in date_str:
                            result.date = datetime.now().strftime("%Y-%m-%d")
                        else:
                            result.date = date_str
                        break

                if result.title and result.url:
                    result.category = self._classify_result(result)
                    result.relevance_score = self._calculate_relevance(result)
                    results.append(result)

            except Exception as e:
                logger.debug(f"[百度] 解析结果异常: {e}")
                continue

        return results

    def _resolve_baidu_url(self, href: str) -> str:
        """解析百度跳转链接 - 仅提取参数中的真实URL，不发额外请求"""
        if "baidu.com/link" in href:
            # 尝试从URL参数中提取真实URL（百度链接格式：?url=xxx 或 &url=xxx）
            parsed = urlparse(href)
            params = parse_qs(parsed.query)
            if "url" in params:
                return params["url"][0]
            # 某些百度链接在 fragment 或 path 中编码
            try:
                from urllib.parse import unquote
                decoded = unquote(href)
                url_match = re.search(r'(https?://[^&\s]+)', decoded)
                if url_match:
                    return url_match.group(1)
            except:
                pass
            # 无法解析则保留原始链接
            return href
        return href


# ==================== 必应搜索 ====================

class BingSearchEngine(BaseSearchEngine):
    """必应搜索引擎"""

    def __init__(self):
        super().__init__("必应", config.SEARCH_SOURCES["bing"]["base_url"])

    def search(self, keyword: str, max_pages: int = 2) -> List[SearchResult]:
        results = []
        for page in range(max_pages):
            first = page * 10 + 1
            url = f"{self.base_url}?q={quote(keyword)}&first={first}&count=10&setlang=zh-Hans"
            logger.info(f"[必应] 搜索: {keyword} (第{page+1}页)")

            html = self._fetch_page(url)
            if not html:
                continue

            page_results = self._parse_bing_results(html, keyword)
            results.extend(page_results)
            self._delay()

        return results

    def _parse_bing_results(self, html: str, keyword: str) -> List[SearchResult]:
        results = []
        soup = BeautifulSoup(html, "html.parser")

        items = soup.select("li.b_algo")
        if not items:
            items = soup.select("#b_results > li")
        if not items:
            # 回退选择器
            items = soup.select("ol#b_results > li")

        for item in items:
            try:
                result = SearchResult(source=self.name, keyword=keyword)

                # 标题提取
                title_tag = item.select_one("h2 a") or item.select_one("h2 > a")
                if title_tag:
                    result.title = title_tag.get_text(strip=True)
                    result.url = title_tag.get("href", "")

                # 摘要提取
                snippet_tag = (
                    item.select_one(".b_caption p")
                    or item.select_one(".b_caption > p")
                    or item.select_one("p")
                )
                if snippet_tag:
                    result.snippet = snippet_tag.get_text(strip=True)

                # 日期提取 - 增强版
                text_content = item.get_text()
                date_patterns = [
                    r'(\d{4}[-/年]\d{1,2}[-/月]\d{1,2}[日]?)',
                    r'(\d+天前|\d+小时前|\d+分钟前|\d+周前)',
                ]
                for pattern in date_patterns:
                    date_match = re.search(pattern, text_content)
                    if date_match:
                        date_str = date_match.group(1)
                        date_str = date_str.replace("年", "-").replace("月", "-").replace("日", "").replace("/", "-")
                        if "天前" in date_str:
                            days = int(re.search(r'(\d+)', date_str).group(1))
                            result.date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
                        elif "小时前" in date_str:
                            result.date = datetime.now().strftime("%Y-%m-%d")
                        elif "分钟前" in date_str:
                            result.date = datetime.now().strftime("%Y-%m-%d")
                        elif "周前" in date_str:
                            weeks = int(re.search(r'(\d+)', date_str).group(1))
                            result.date = (datetime.now() - timedelta(weeks=weeks)).strftime("%Y-%m-%d")
                        else:
                            result.date = date_str
                        break

                if result.title and result.url:
                    result.category = self._classify_result(result)
                    result.relevance_score = self._calculate_relevance(result)
                    results.append(result)

            except Exception as e:
                logger.debug(f"[必应] 解析结果异常: {e}")
                continue

        return results


# ==================== 招标网站搜索 ====================

class BidSiteSearchEngine(BaseSearchEngine):
    """招标网站搜索引擎 - 聚合多个招标平台"""

    def __init__(self):
        super().__init__("招标网站", "")
        self.platforms = {
            "chinabidding": "https://search.chinabidding.cn/search",
            "zhaobiao": "https://www.zhaobiao.cn/search",
        }

    def search(self, keyword: str, max_pages: int = 2) -> List[SearchResult]:
        results = []
        # 通过必应搜索招标网站内容（必应更稳定，反爬较轻）
        search_queries = [
            f'site:chinabidding.cn {keyword}',
            f'site:zhaobiao.cn {keyword}',
            f'site:bidcenter.com.cn {keyword}',
        ]

        bing = BingSearchEngine()
        for query in search_queries:
            logger.info(f"[招标网站] 通过必应搜索: {query}")
            try:
                site_results = bing.search(query, max_pages=1)
                for r in site_results:
                    r.source = "招标网站"
                    r.keyword = keyword
                    r.category = self._classify_result(r)
                    r.relevance_score = self._calculate_relevance(r)
                results.extend(site_results)
            except Exception as e:
                logger.warning(f"[招标网站] 搜索失败: {e}")
            self._delay()

        return results


# ==================== 搜索调度器 ====================

class SearchScheduler:
    """搜索调度器 - 协调所有搜索引擎"""

    def __init__(self):
        self.engines: Dict[str, BaseSearchEngine] = {}
        self._init_engines()

    def _init_engines(self):
        """初始化搜索引擎"""
        if config.SEARCH_SOURCES["baidu"]["enabled"]:
            self.engines["baidu"] = BaiduSearchEngine()
        if config.SEARCH_SOURCES["bing"]["enabled"]:
            self.engines["bing"] = BingSearchEngine()
        if config.SEARCH_SOURCES["chinabidding"]["enabled"] or config.SEARCH_SOURCES["zhaobiao"]["enabled"]:
            self.engines["bidsite"] = BidSiteSearchEngine()

    def run_search(self, keywords: List[str] = None, max_pages: int = 2) -> SearchReport:
        """执行搜索任务"""
        if keywords is None:
            keywords = config.ALL_KEYWORDS

        report = SearchReport(
            search_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            total_keywords=len(keywords),
        )

        all_results: List[SearchResult] = []
        seen_uids: Set[str] = set()

        logger.info(f"🚀 开始搜索，共 {len(keywords)} 个关键词，{len(self.engines)} 个搜索引擎")

        for i, keyword in enumerate(keywords, 1):
            logger.info(f"\n{'='*60}")
            logger.info(f"📋 关键词 [{i}/{len(keywords)}]: {keyword}")
            logger.info(f"{'='*60}")

            for engine_name, engine in self.engines.items():
                try:
                    max_p = config.SEARCH_SOURCES.get(engine_name, {}).get("max_pages", max_pages)
                    if engine_name == "bidsite":
                        max_p = 1
                    results = engine.search(keyword, max_pages=max_p)
                    logger.info(f"  ✅ [{engine.name}] 找到 {len(results)} 条结果")

                    # 去重
                    new_count = 0
                    for r in results:
                        if r.uid not in seen_uids:
                            seen_uids.add(r.uid)
                            all_results.append(r)
                            new_count += 1
                    logger.info(f"  📊 去重后新增 {new_count} 条")

                    report.total_searched += 1

                except Exception as e:
                    error_msg = f"[{engine.name}] 搜索 '{keyword}' 失败: {e}"
                    logger.error(f"  ❌ {error_msg}")
                    report.errors.append(error_msg)

        # 过滤结果
        filtered_results = self._filter_results(all_results)

        # 按相关度排序
        filtered_results.sort(key=lambda x: x.relevance_score, reverse=True)

        # 统计
        report.results = filtered_results
        report.total_results = len(filtered_results)
        report.source_stats = self._count_by_source(filtered_results)
        report.category_stats = self._count_by_category(filtered_results)

        logger.info(f"\n{'='*60}")
        logger.info(f"🎯 搜索完成！共找到 {report.total_results} 条有效结果")
        logger.info(f"{'='*60}")

        return report

    def _filter_results(self, results: List[SearchResult]) -> List[SearchResult]:
        """过滤搜索结果"""
        filtered = []
        for r in results:
            text = (r.title + " " + r.snippet).lower()

            # 排除不相关结果
            if any(ex in text for ex in config.EXCLUDE_KEYWORDS):
                continue

            # 必须包含至少一个核心词
            if not any(kw in text for kw in config.MUST_CONTAIN_ANY):
                continue

            # 相关度阈值
            if r.relevance_score < 20:
                continue

            # URL 去重补充检查（同域名+相似标题）
            filtered.append(r)

        return filtered

    def _count_by_source(self, results: List[SearchResult]) -> Dict[str, int]:
        stats = {}
        for r in results:
            stats[r.source] = stats.get(r.source, 0) + 1
        return stats

    def _count_by_category(self, results: List[SearchResult]) -> Dict[str, int]:
        stats = {}
        for r in results:
            stats[r.category] = stats.get(r.category, 0) + 1
        return stats
