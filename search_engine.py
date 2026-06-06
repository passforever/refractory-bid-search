"""
耐火材料招标采购信息搜索工具 - 核心搜索引擎
支持多源搜索、关键词组合、日期过滤、结果去重、API数据源
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

def _get_app_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

sys.path.insert(0, _get_app_dir())

import requests
from bs4 import BeautifulSoup

import config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ==================== 数据模型 ====================

@dataclass
class SearchResult:
    """单条搜索结果 - 增强版，含更多字段"""
    title: str = ""
    url: str = ""
    snippet: str = ""
    source: str = ""
    keyword: str = ""
    date: str = ""
    category: str = ""
    relevance_score: float = 0.0
    # 新增字段 - 更多信息
    publisher: str = ""      # 发布单位/采购人
    budget: str = ""         # 预算金额
    deadline: str = ""       # 投标截止日期
    region: str = ""         # 地区
    bid_type: str = ""       # 招标类型（公开招标/竞争性谈判/询价等）
    contact: str = ""        # 联系方式
    domain: str = ""         # 来源域名
    snippet_full: str = ""   # 完整摘要（不限长度）

    @property
    def uid(self) -> str:
        parsed = urlparse(self.url)
        key = f"{parsed.netloc}{parsed.path}"
        return hashlib.md5(key.encode()).hexdigest()

    def extract_extra_info(self):
        """从标题和摘要中提取额外信息"""
        text = f"{self.title} {self.snippet}"

        # 提取预算金额
        budget_patterns = [
            r'预算[金额]?[：:]\s*([\d,.]+)\s*万?元',
            r'金额[：:]\s*([\d,.]+)\s*万?元',
            r'([\d,.]+)\s*万元',
            r'预算[金额]?[：:]\s*([\d,.]+)',
        ]
        for pat in budget_patterns:
            m = re.search(pat, text)
            if m:
                val = m.group(1)
                if '万' not in text[m.start():m.end()] and float(val.replace(',','')) < 100:
                    val += '万元'
                elif '万' in text[m.start():m.end()]:
                    val += '万元'
                else:
                    val += '元'
                self.budget = val
                break

        # 提取截止日期
        deadline_patterns = [
            r'(?:截止|开标)[时间日期][：:]\s*(\d{4}[-/年]\d{1,2}[-/月]\d{1,2}[日]?\s*\d{0,2}[：:]?\d{0,2})',
            r'(\d{4}[-/年]\d{1,2}[-/月]\d{1,2}[日]?)\s*(?:截止|开标|投标)',
        ]
        for pat in deadline_patterns:
            m = re.search(pat, text)
            if m:
                self.deadline = m.group(1).replace("年","-").replace("月","-").replace("日","").replace("/","-")
                break

        # 提取地区
        regions = ["北京","上海","天津","重庆","河北","山西","辽宁","吉林","黑龙江",
                   "江苏","浙江","安徽","福建","江西","山东","河南","湖北","湖南",
                   "广东","海南","四川","贵州","云南","陕西","甘肃","青海","台湾",
                   "内蒙古","广西","西藏","宁夏","新疆","香港","澳门"]
        for r in regions:
            if r in text:
                self.region = r
                break

        # 提取招标类型
        bid_types = {
            "公开招标": ["公开招标"],
            "邀请招标": ["邀请招标"],
            "竞争性谈判": ["竞争性谈判"],
            "竞争性磋商": ["竞争性磋商"],
            "询价采购": ["询价", "询价采购"],
            "单一来源": ["单一来源"],
            "比选": ["比选"],
        }
        for btype, patterns in bid_types.items():
            if any(p in text for p in patterns):
                self.bid_type = btype
                break

        # 提取发布单位
        pub_patterns = [
            r'(?:采购人|采购单位|招标人|业主|采购方)[：:]\s*([^\s,，。；;]+)',
            r'([^\s,，。；;]+(?:公司|集团|厂|局|院|中心|部|处|站|所))',
        ]
        for pat in pub_patterns:
            m = re.search(pat, text)
            if m:
                candidate = m.group(1)
                if len(candidate) > 3 and len(candidate) < 30:
                    self.publisher = candidate
                    break

        # 提取域名
        if self.url:
            try:
                parsed = urlparse(self.url)
                self.domain = parsed.netloc
            except:
                pass

        # 保存完整摘要
        self.snippet_full = self.snippet


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
    def __init__(self, name: str, base_url: str):
        self.name = name
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update(config.HEADERS)

    def _delay(self):
        delay = random.uniform(config.REQUEST_DELAY_MIN, config.REQUEST_DELAY_MAX)
        time.sleep(delay)

    def _fetch_page(self, url: str, encoding: str = "utf-8") -> Optional[str]:
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
        raise NotImplementedError

    def _classify_result(self, result: SearchResult) -> str:
        text = (result.title + " " + result.snippet).lower()
        if any(k in text for k in ["维修", "检修", "砌筑", "施工", "筑炉"]):
            return "窑炉维修"
        if any(k in text for k in ["高铝砖", "粘土砖", "轻质砖", "硅砖", "浇注料", "不定型", "泥浆", "散料", "可塑料", "喷涂料"]):
            return "材料采购"
        return "招标采购"

    def _calculate_relevance(self, result: SearchResult) -> float:
        score = 50.0
        text = (result.title + " " + result.snippet).lower()

        high_value = ["耐火", "招标", "采购", "中标", "高铝砖", "硅砖", "浇注料"]
        for kw in high_value:
            if kw in text:
                score += 10

        furnaces = ["高炉", "热风炉", "焦炉", "窑炉", "加热炉", "回转窑"]
        for kw in furnaces:
            if kw in text:
                score += 8

        if result.date:
            try:
                pub_date = datetime.strptime(result.date[:10], "%Y-%m-%d")
                days_ago = (datetime.now() - pub_date).days
                if days_ago <= 3: score += 20
                elif days_ago <= 7: score += 15
                elif days_ago <= 14: score += 10
                elif days_ago <= 30: score += 5
            except (ValueError, IndexError):
                pass

        for ex in config.EXCLUDE_KEYWORDS:
            if ex in text:
                score -= 30

        return max(0, min(100, score))


# ==================== 百度搜索 ====================

class BaiduSearchEngine(BaseSearchEngine):
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

        items = soup.select("div.result, div.c-container")
        if not items:
            items = soup.select("div[class*='result']")
        if not items:
            items = soup.select("#content_left > div")
        if not items:
            items = [div for div in soup.find_all("div") if div.find("h3") and div.find("a")]

        for item in items:
            try:
                result = SearchResult(source=self.name, keyword=keyword)

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
                        result.url = self._resolve_baidu_url(href)

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
                    all_text = item.get_text(separator=" ", strip=True)
                    snippet = all_text.replace(result.title, "", 1).strip()
                    if len(snippet) > 500:
                        snippet = snippet[:500] + "..."
                    result.snippet = snippet

                text_content = item.get_text()
                date_patterns = [
                    r'(\d{4}[-/年]\d{1,2}[-/月]\d{1,2}[日]?)',
                    r'(\d{1,2}[-/月]\d{1,2}[日]?\s*\d{4})',
                    r'(\d+天前|\d+小时前|\d+分钟前)',
                ]
                for pattern in date_patterns:
                    date_match = re.search(pattern, text_content)
                    if date_match:
                        date_str = date_match.group(1)
                        date_str = date_str.replace("年","-").replace("月","-").replace("日","").replace("/","-")
                        if "天前" in date_str:
                            days = int(re.search(r'(\d+)', date_str).group(1))
                            result.date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
                        elif "小时前" in date_str:
                            result.date = datetime.now().strftime("%Y-%m-%d")
                        elif "分钟前" in date_str:
                            result.date = datetime.now().strftime("%Y-%m-%d")
                        else:
                            result.date = date_str
                        break

                if result.title and result.url:
                    result.category = self._classify_result(result)
                    result.relevance_score = self._calculate_relevance(result)
                    result.extract_extra_info()
                    results.append(result)

            except Exception as e:
                logger.debug(f"[百度] 解析结果异常: {e}")
                continue

        return results

    def _resolve_baidu_url(self, href: str) -> str:
        if "baidu.com/link" in href:
            parsed = urlparse(href)
            params = parse_qs(parsed.query)
            if "url" in params:
                return params["url"][0]
            try:
                from urllib.parse import unquote
                decoded = unquote(href)
                url_match = re.search(r'(https?://[^&\s]+)', decoded)
                if url_match:
                    return url_match.group(1)
            except:
                pass
            return href
        return href


# ==================== 必应搜索 ====================

class BingSearchEngine(BaseSearchEngine):
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
            items = soup.select("ol#b_results > li")

        for item in items:
            try:
                result = SearchResult(source=self.name, keyword=keyword)

                title_tag = item.select_one("h2 a") or item.select_one("h2 > a")
                if title_tag:
                    result.title = title_tag.get_text(strip=True)
                    result.url = title_tag.get("href", "")

                snippet_tag = (
                    item.select_one(".b_caption p")
                    or item.select_one(".b_caption > p")
                    or item.select_one("p")
                )
                if snippet_tag:
                    result.snippet = snippet_tag.get_text(strip=True)

                text_content = item.get_text()
                date_patterns = [
                    r'(\d{4}[-/年]\d{1,2}[-/月]\d{1,2}[日]?)',
                    r'(\d+天前|\d+小时前|\d+分钟前|\d+周前)',
                ]
                for pattern in date_patterns:
                    date_match = re.search(pattern, text_content)
                    if date_match:
                        date_str = date_match.group(1)
                        date_str = date_str.replace("年","-").replace("月","-").replace("日","").replace("/","-")
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
                    result.extract_extra_info()
                    results.append(result)

            except Exception as e:
                logger.debug(f"[必应] 解析结果异常: {e}")
                continue

        return results


# ==================== 招标网站搜索 ====================

class BidSiteSearchEngine(BaseSearchEngine):
    def __init__(self):
        super().__init__("招标网站", "")

    def search(self, keyword: str, max_pages: int = 2) -> List[SearchResult]:
        results = []
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
                    r.extract_extra_info()
                results.extend(site_results)
            except Exception as e:
                logger.warning(f"[招标网站] 搜索失败: {e}")
            self._delay()

        return results


# ==================== API 数据源搜索 ====================

class ApiSearchEngine(BaseSearchEngine):
    """通过配置的 API 数据源搜索结构化招标数据"""

    def __init__(self):
        super().__init__("API数据源", "")

    def search(self, keyword: str, max_pages: int = 1) -> List[SearchResult]:
        results = []
        api_sources = config.ConfigManager.get_api_sources()

        for key, source_cfg in api_sources.items():
            if not source_cfg.get("enabled", False):
                continue

            logger.info(f"[API] 搜索 {source_cfg.get('name', key)}: {keyword}")
            try:
                api_results = self._search_api(key, source_cfg, keyword)
                results.extend(api_results)
            except Exception as e:
                logger.warning(f"[API] {source_cfg.get('name', key)} 搜索失败: {e}")
            self._delay()

        return results

    def _search_api(self, key: str, source_cfg: dict, keyword: str) -> List[SearchResult]:
        """根据 API 配置搜索"""
        results = []
        api_url = source_cfg.get("api_url", "")
        api_type = source_cfg.get("api_type", "html")
        params_template = source_cfg.get("params", {})
        encoding = source_cfg.get("encoding", "utf-8")
        selectors = source_cfg.get("result_selector", {})

        # 构建请求参数
        params = {}
        today = datetime.now().strftime("%Y:%m:%d")
        date_30d_ago = (datetime.now() - timedelta(days=30)).strftime("%Y:%m:%d")
        for k, v in params_template.items():
            v = str(v).replace("{keyword}", keyword).replace("{today}", today).replace("{date_30d_ago}", date_30d_ago)
            params[k] = v

        if api_type == "json":
            # JSON API
            try:
                resp = self.session.get(api_url, params=params, timeout=config.REQUEST_TIMEOUT)
                resp.encoding = encoding
                if resp.status_code == 200:
                    data = resp.json()
                    # 通用 JSON 解析 - 尝试提取列表
                    items = self._extract_json_list(data)
                    for item in items[:20]:
                        result = SearchResult(source=source_cfg.get("name", key), keyword=keyword)
                        if isinstance(item, dict):
                            result.title = str(item.get("title", item.get("name", "")))
                            result.url = str(item.get("url", item.get("link", item.get("href", ""))))
                            result.snippet = str(item.get("snippet", item.get("description", item.get("content", item.get("summary", "")))))
                            result.date = str(item.get("date", item.get("publishDate", item.get("pubDate", ""))))[:10]
                            result.publisher = str(item.get("buyer", item.get("purchaser", item.get("company", ""))))
                            result.budget = str(item.get("budget", item.get("amount", "")))
                            result.deadline = str(item.get("deadline", item.get("endDate", "")))
                            result.region = str(item.get("region", item.get("area", item.get("province", ""))))
                            if result.title and result.url:
                                result.category = self._classify_result(result)
                                result.relevance_score = self._calculate_relevance(result)
                                result.extract_extra_info()
                                results.append(result)
            except Exception as e:
                logger.warning(f"[API] JSON 解析失败: {e}")

        else:
            # HTML 页面爬取
            try:
                if params:
                    url = api_url + "?" + "&".join(f"{k}={quote(str(v))}" for k, v in params.items())
                else:
                    url = api_url + "?kw=" + quote(keyword)

                html = self._fetch_page(url, encoding)
                if not html:
                    return results

                soup = BeautifulSoup(html, "html.parser")
                container_sel = selectors.get("container", "div")
                containers = soup.select(container_sel)

                for container in containers[:20]:
                    result = SearchResult(source=source_cfg.get("name", key), keyword=keyword)

                    # 标题
                    title_sel = selectors.get("title", "a")
                    title_tag = container.select_one(title_sel)
                    if title_tag:
                        result.title = title_tag.get_text(strip=True)

                    # URL
                    url_sel = selectors.get("url", "a[href]")
                    url_tag = container.select_one(url_sel)
                    if url_tag:
                        href = url_tag.get("href", "")
                        if href and not href.startswith("http"):
                            href = urljoin(api_url, href)
                        result.url = href

                    # 摘要
                    snippet_sel = selectors.get("snippet", "p")
                    snippet_tag = container.select_one(snippet_sel)
                    if snippet_tag:
                        result.snippet = snippet_tag.get_text(strip=True)

                    # 日期
                    date_sel = selectors.get("date", "span")
                    date_tag = container.select_one(date_sel)
                    if date_tag:
                        result.date = date_tag.get_text(strip=True)[:10]

                    if result.title and result.url:
                        result.category = self._classify_result(result)
                        result.relevance_score = self._calculate_relevance(result)
                        result.extract_extra_info()
                        results.append(result)

            except Exception as e:
                logger.warning(f"[API] HTML 解析失败: {e}")

        return results

    def _extract_json_list(self, data):
        """从 JSON 响应中提取列表数据"""
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            # 尝试常见字段名
            for key in ["data", "results", "items", "list", "records", "rows", "content"]:
                if key in data:
                    val = data[key]
                    if isinstance(val, list):
                        return val
                    if isinstance(val, dict):
                        return self._extract_json_list(val)
            # 遍历所有值找列表
            for v in data.values():
                if isinstance(v, list) and len(v) > 0:
                    return v
        return []


# ==================== 搜索调度器 ====================

class SearchScheduler:
    def __init__(self):
        self.engines: Dict[str, BaseSearchEngine] = {}
        self._init_engines()

    def _init_engines(self):
        if config.SEARCH_SOURCES["baidu"]["enabled"]:
            self.engines["baidu"] = BaiduSearchEngine()
        if config.SEARCH_SOURCES["bing"]["enabled"]:
            self.engines["bing"] = BingSearchEngine()
        if config.SEARCH_SOURCES["chinabidding"]["enabled"] or config.SEARCH_SOURCES["zhaobiao"]["enabled"]:
            self.engines["bidsite"] = BidSiteSearchEngine()

        # 检查是否有启用的 API 数据源
        api_sources = config.ConfigManager.get_api_sources()
        has_enabled_api = any(s.get("enabled", False) for s in api_sources.values())
        if has_enabled_api:
            self.engines["api"] = ApiSearchEngine()

    def run_search(self, keywords: List[str] = None, max_pages: int = 2) -> SearchReport:
        if keywords is None:
            keywords = config.ConfigManager.get_keywords()

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
                    elif engine_name == "api":
                        max_p = 1
                    results = engine.search(keyword, max_pages=max_p)
                    logger.info(f"  ✅ [{engine.name}] 找到 {len(results)} 条结果")

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

        filtered_results = self._filter_results(all_results)
        filtered_results.sort(key=lambda x: x.relevance_score, reverse=True)

        report.results = filtered_results
        report.total_results = len(filtered_results)
        report.source_stats = self._count_by_source(filtered_results)
        report.category_stats = self._count_by_category(filtered_results)

        logger.info(f"\n{'='*60}")
        logger.info(f"🎯 搜索完成！共找到 {report.total_results} 条有效结果")
        logger.info(f"{'='*60}")

        return report

    def _filter_results(self, results: List[SearchResult]) -> List[SearchResult]:
        filtered = []
        for r in results:
            text = (r.title + " " + r.snippet).lower()
            if any(ex in text for ex in config.EXCLUDE_KEYWORDS):
                continue
            if not any(kw in text for kw in config.MUST_CONTAIN_ANY):
                continue
            if r.relevance_score < 20:
                continue
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
