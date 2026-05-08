import json
import re
import time
from urllib.parse import quote
from urllib.request import Request, urlopen

from .models import FundSnapshot


def fetch_text(url):
    """读取远端文本。基金公开接口偶尔会拦截非浏览器 UA。"""
    req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(req, timeout=10) as resp:
        return resp.read().decode("utf-8", errors="replace")


def parse_jsonp(text):
    """把 callback({...}) 形式的 JSONP 转成 Python dict。"""
    match = re.search(r"^[^(]*\((.*)\)\s*;?\s*$", text, re.S)
    if not match:
        raise ValueError("接口未返回 JSONP 数据")
    return json.loads(match.group(1))


def search_funds(keyword):
    """搜索基金，返回东方财富基金候选列表。"""
    keyword = str(keyword).strip()
    url = (
        "https://fundsuggest.eastmoney.com/FundSearch/api/FundSearchAPI.ashx"
        f"?m=1&key={quote(keyword)}&callback=cb&_={int(time.time() * 1000)}"
    )
    data = parse_jsonp(fetch_text(url))
    return [
        item for item in data.get("Datas", [])
        if str(item.get("CATEGORY")) == "700" or item.get("CATEGORYDESC") == "基金"
    ]


def resolve_fund_code(keyword):
    """支持用基金代码或基金名称定位基金代码。名称搜索优先匹配同名和同份额类别。"""
    keyword = str(keyword).strip()
    if re.fullmatch(r"\d{6}", keyword):
        return keyword

    funds = search_funds(keyword)
    if not funds:
        raise ValueError(f"未找到基金：{keyword}")
    return choose_best_fund(keyword, funds)["CODE"]


def choose_best_fund(keyword, funds):
    """从搜索候选中挑选最接近用户输入的基金。

    表格里常写“混合C”，搜索接口可能把 A 类排在前面，所以这里显式优先同后缀。
    """
    normalized_keyword = _normalize_name(keyword)

    for fund in funds:
        names = _candidate_names(fund)
        if normalized_keyword in {_normalize_name(name) for name in names if name}:
            return fund

    suffix = _share_class_suffix(keyword)
    if suffix:
        same_suffix = [
            fund for fund in funds
            if any(_share_class_suffix(name) == suffix for name in _candidate_names(fund))
        ]
        if same_suffix:
            return same_suffix[0]

    return funds[0]


def fetch_estimate(code):
    """查询天天基金估值接口，返回原始字段。"""
    url = f"https://fundgz.1234567.com.cn/js/{code}.js?rt={int(time.time() * 1000)}"
    data = parse_jsonp(fetch_text(url))
    if not data:
        raise ValueError(f"未获取到估值数据：{code}")
    return data


def fetch_confirmed_nav(code):
    """查询腾讯基金接口里的最新确认净值。"""
    text = fetch_text(f"https://qt.gtimg.cn/q=jj{code}")
    match = re.search(r'v_jj\d+="(.*)"\s*;?\s*$', text)
    if not match:
        return None
    parts = match.group(1).split("~")
    if len(parts) < 9:
        return None
    latest_nav = _to_float(parts[5])
    change_percent = _to_float(parts[7])
    nav_date = parts[8].strip()
    if latest_nav is None or not nav_date:
        return None
    return {
        "latest_nav": latest_nav,
        "nav_date": nav_date[:10],
        "change_percent": change_percent,
    }


def fetch_fund_snapshot(keyword):
    """查询基金名称、最新净值日期、最新净值和估值涨跌幅。"""
    sector_tags = []
    if re.fullmatch(r"\d{6}", str(keyword).strip()):
        code = str(keyword).strip()
    else:
        funds = search_funds(keyword)
        if not funds:
            raise ValueError(f"未找到基金：{keyword}")
        fund = choose_best_fund(keyword, funds)
        code = fund["CODE"]
        sector_tags = _sector_tags_from_fund(fund)
    data = fetch_estimate(code)
    latest_nav = _to_float(data.get("dwjz"))
    nav_date = data.get("jzrq", "")
    yesterday_change_percent = _to_float(data.get("gszzl"))
    estimated_nav = _to_float(data.get("gsz"))
    estimated_change_percent = _to_float(data.get("gszzl"))
    estimated_time = data.get("gztime")

    confirmed_nav = fetch_confirmed_nav(code)
    if confirmed_nav and (not nav_date or confirmed_nav["nav_date"] > nav_date):
        latest_nav = confirmed_nav["latest_nav"]
        nav_date = confirmed_nav["nav_date"]
        yesterday_change_percent = confirmed_nav["change_percent"]

    if estimated_time and nav_date and estimated_time[:10] <= nav_date:
        estimated_nav = None
        estimated_change_percent = None
        estimated_time = None

    if latest_nav is None:
        latest_nav = estimated_nav
    if latest_nav is None:
        raise ValueError(f"未获取到可用净值：{code}")

    return FundSnapshot(
        code=data.get("fundcode", code),
        name=data.get("name", ""),
        latest_nav=latest_nav,
        nav_date=nav_date,
        yesterday_change_percent=yesterday_change_percent,
        estimated_nav=estimated_nav,
        estimated_change_percent=estimated_change_percent,
        estimated_time=estimated_time,
        sector_tags=sector_tags,
    )


def _to_float(value):
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _candidate_names(fund):
    base = fund.get("FundBaseInfo") or {}
    names = [fund.get("NAME"), base.get("SHORTNAME")]
    other = base.get("OTHERNAME") or ""
    names.extend(part.strip() for part in other.split(",") if part.strip())
    return names


def _normalize_name(value):
    return re.sub(r"\s+", "", str(value or ""))


def _share_class_suffix(value):
    normalized = _normalize_name(value)
    match = re.search(r"([A-Z])$", normalized)
    if match and match.group(1) in {"A", "B", "C", "D", "E", "I", "Y"}:
        return match.group(1)
    return None


def _sector_tags_from_fund(fund):
    tags = []
    for item in fund.get("ZTJJInfo") or []:
        name = item.get("TTYPENAME")
        if name and name not in tags:
            tags.append(name)
    return tags
