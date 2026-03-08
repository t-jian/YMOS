#!/usr/bin/env python3
"""
YMOS Finnhub 数据获取工具（投资场景示例）

【本脚本是投资研究场景的实现示例】
- 数据源：Finnhub.io 金融数据 API
- 数据类型：市场新闻、个股新闻、实时行情、盈利日历

【Finnhub API 概览】
  官方文档：https://finnhub.io/docs/api/
  免费注册：https://finnhub.io/  （注册后在 Dashboard 获取 API Key）
  免费额度：60 次/分钟
  认证方式：URL 参数 ?token=YOUR_KEY  或  Header X-Finnhub-Token

  本脚本使用的核心 Endpoints：
    GET /news              → 市场大盘新闻（category: general/forex/crypto/merger）
    GET /company-news      → 个股最新新闻（symbol + from/to 日期范围）
    GET /quote             → 股票实时行情（c=当前价, dp=涨跌幅%, d=涨跌额）
    GET /calendar/earnings → 盈利发布日历（from/to 日期范围）

【其他场景如何适配】
本脚本是三层架构「第一层：信息输入」的具体实现。
如果你是其他领域的知识工作者，可以参考本脚本的结构，替换为你的 API：
- 学术研究 → Semantic Scholar API / PubMed API
- 产品经理 → Product Hunt API / GitHub Trending API
- 内容创作 → Reddit API / Hacker News API

核心不变：通过配置化的脚本自动拉取数据到本地
核心可变：API endpoint、查询参数、数据格式、存储路径
"""

import urllib.request
import urllib.parse
import urllib.error
import argparse
import json
import ssl
import sys
from datetime import datetime, timedelta, timezone

# ============================================================
# 📌 在这里填入你的 Finnhub API Key
#    前往 https://finnhub.io/ 免费注册获取（有免费套餐）
# ============================================================
API_KEY = ""

# Finnhub REST API 基础地址
FINNHUB_BASE = "https://finnhub.io/api/v1"

# ============================================================
# 关注的股票列表（替换为你实际关注的标的，支持美股 Ticker）
# ============================================================
WATCHLIST = ["AAPL", "NVDA", "TSLA", "MSFT", "AMZN"]

# 市场大盘新闻分类
# 可选值：general | forex | crypto | merger
NEWS_CATEGORIES = ["general", "merger"]


# ─────────────────────────────────────────────
# 工具函数
# ─────────────────────────────────────────────

def check_api_key():
    """检查 API Key 是否已配置"""
    if not API_KEY:
        print("=" * 55)
        print("⚠️  Finnhub API Key 未配置")
        print("=" * 55)
        print()
        print("你需要一个 Finnhub API Key 才能使用此脚本。")
        print()
        print("📡 免费获取 API Key（有免费套餐，无需信用卡）：")
        print("   https://finnhub.io/")
        print("   注册后进入 Dashboard → 复制 API Key")
        print()
        print("🆓 不需要 API Key 的替代方案：")
        print("   使用 fetch_rss.py 通过免费 RSS 订阅获取数据")
        print("   python3 scripts/fetch_rss.py 1 --output output.json")
        print()
        print("配置方法：")
        print('   编辑 scripts/fetch_data_api.py，将 API_KEY = "" 改为你的 Key')
        print()
        sys.exit(1)


def finnhub_get(endpoint, params=None):
    """
    向 Finnhub API 发起 GET 请求（核心请求函数）

    认证方式：在 URL 参数中追加 token=API_KEY
    示例 URL：https://finnhub.io/api/v1/quote?symbol=AAPL&token=YOUR_KEY

    Args:
        endpoint: API 路径，如 "/news" 或 "/quote"
        params:   额外的 query 参数字典（token 会自动追加）

    Returns:
        解析后的 JSON 数据（dict 或 list），失败返回 None
    """
    query = {"token": API_KEY}
    if params:
        query.update(params)

    url = f"{FINNHUB_BASE}{endpoint}?{urllib.parse.urlencode(query)}"

    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "YMOS/1.0",
            "Accept": "application/json",
        },
        method="GET",
    )

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    try:
        with urllib.request.urlopen(req, context=ctx, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))

    except urllib.error.HTTPError as e:
        print(f"   ❌ HTTP {e.code} — {endpoint}")
        if e.code == 401:
            print("     → API Key 无效或已过期，请检查 https://finnhub.io/dashboard")
        elif e.code == 429:
            print("     → 超出频率限制（免费套餐 60次/分钟），请稍后再试")
        return None

    except urllib.error.URLError as e:
        print(f"   ❌ 网络错误: {e.reason}")
        return None

    except Exception as e:
        print(f"   ❌ 未知错误: {e}")
        return None


# ─────────────────────────────────────────────
# 数据获取函数
# ─────────────────────────────────────────────

def fetch_market_news(days=1):
    """
    获取市场大盘新闻

    Finnhub Endpoint：GET /news
      文档：https://finnhub.io/docs/api/market-news
      参数：category（必填）, minId（可选，用于分页）

    category 可选值：
      general  → 综合市场新闻
      forex    → 外汇新闻
      crypto   → 加密货币新闻
      merger   → 并购重组新闻

    返回字段（每条新闻）：
      headline  → 标题
      summary   → 摘要
      source    → 来源媒体
      url       → 原文链接
      datetime  → 发布时间（Unix timestamp）
      related   → 相关股票 Ticker
      image     → 配图 URL
    """
    print(f"\n📰 获取市场大盘新闻（最近 {days} 天，分类: {NEWS_CATEGORIES}）...")
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).timestamp()

    all_items = []
    for category in NEWS_CATEGORIES:
        data = finnhub_get("/news", {"category": category})

        if not data or not isinstance(data, list):
            print(f"   ⚠️ [{category}] 未获取到数据")
            continue

        filtered = [
            {
                "type": "market_news",
                "category": category,
                "headline": item.get("headline", ""),
                "summary": item.get("summary", ""),
                "source": item.get("source", ""),
                "url": item.get("url", ""),
                "datetime": datetime.fromtimestamp(
                    item.get("datetime", 0), tz=timezone.utc
                ).isoformat(),
                "related": item.get("related", ""),
            }
            for item in data
            if item.get("datetime", 0) >= cutoff
        ]
        all_items.extend(filtered)
        print(f"   [{category}] → {len(filtered)} 条")

    print(f"   ✅ 市场新闻合计 {len(all_items)} 条")
    return all_items


def fetch_company_news(symbol, days=1):
    """
    获取特定股票的最新新闻

    Finnhub Endpoint：GET /company-news
      文档：https://finnhub.io/docs/api/company-news
      参数：
        symbol  → 股票 Ticker，如 "AAPL"
        from    → 开始日期，格式 "YYYY-MM-DD"
        to      → 结束日期，格式 "YYYY-MM-DD"

    返回字段与 /news 相同，额外包含 id（新闻唯一 ID）
    """
    date_to   = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    date_from = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")

    data = finnhub_get("/company-news", {
        "symbol": symbol,
        "from": date_from,
        "to":   date_to,
    })

    if not data or not isinstance(data, list):
        return []

    return [
        {
            "type": "company_news",
            "symbol": symbol,
            "category": item.get("category", ""),
            "headline": item.get("headline", ""),
            "summary": item.get("summary", ""),
            "source": item.get("source", ""),
            "url": item.get("url", ""),
            "datetime": datetime.fromtimestamp(
                item.get("datetime", 0), tz=timezone.utc
            ).isoformat(),
        }
        for item in data
    ]


def fetch_quotes(symbols):
    """
    获取股票实时行情

    Finnhub Endpoint：GET /quote
      文档：https://finnhub.io/docs/api/quote
      参数：symbol → 股票 Ticker，如 "AAPL"

    返回字段：
      c   → 当前价格（Current price）
      d   → 涨跌额（Change）
      dp  → 涨跌幅，单位 %（Percent change）
      h   → 今日最高价（High）
      l   → 今日最低价（Low）
      o   → 今日开盘价（Open）
      pc  → 昨日收盘价（Previous close）
      t   → 更新时间戳（Unix timestamp）
    """
    print(f"\n📊 获取实时行情：{', '.join(symbols)}")
    quotes = []

    for symbol in symbols:
        data = finnhub_get("/quote", {"symbol": symbol})

        if not data or data.get("c", 0) == 0:
            print(f"   ⚠️ {symbol}: 暂无行情（非交易时段或 Ticker 有误）")
            continue

        pct = data.get("dp", 0) or 0
        direction = "📈" if pct >= 0 else "📉"
        sign = "+" if pct >= 0 else ""
        print(f"   {direction} {symbol}: ${data['c']:.2f}  ({sign}{pct:.2f}%)")

        quotes.append({
            "type": "quote",
            "symbol": symbol,
            "price":      data.get("c"),
            "change":     data.get("d"),
            "change_pct": data.get("dp"),
            "high":       data.get("h"),
            "low":        data.get("l"),
            "open":       data.get("o"),
            "prev_close": data.get("pc"),
            "timestamp":  data.get("t"),
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        })

    return quotes


def fetch_earnings_calendar(days=7):
    """
    获取即将发布的盈利日历（Earnings Calendar）

    Finnhub Endpoint：GET /calendar/earnings
      文档：https://finnhub.io/docs/api/earnings-calendar
      参数：
        from   → 开始日期，格式 "YYYY-MM-DD"
        to     → 结束日期，格式 "YYYY-MM-DD"
        symbol → （可选）过滤特定股票

    返回字段（earningsCalendar 数组内）：
      symbol         → 股票 Ticker
      date           → 盈利发布日期
      epsEstimate    → EPS 预期值
      epsActual      → EPS 实际值（已发布后有值）
      revenueEstimate → 营收预期
      revenueActual   → 营收实际值
      quarter        → 财务季度
      year           → 财务年份
    """
    print(f"\n📅 获取盈利日历（未来 {days} 天）...")
    date_from = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    date_to   = (datetime.now(timezone.utc) + timedelta(days=days)).strftime("%Y-%m-%d")

    data = finnhub_get("/calendar/earnings", {
        "from": date_from,
        "to":   date_to,
    })

    if not data or "earningsCalendar" not in data:
        print("   ⚠️ 未获取到盈利日历数据")
        return []

    calendar = data["earningsCalendar"]

    # 仅保留关注列表内的个股
    filtered = [
        {
            "type": "earnings",
            "symbol": item.get("symbol", ""),
            "date": item.get("date", ""),
            "eps_estimate": item.get("epsEstimate"),
            "eps_actual": item.get("epsActual"),
            "revenue_estimate": item.get("revenueEstimate"),
            "revenue_actual": item.get("revenueActual"),
            "quarter": item.get("quarter"),
            "year": item.get("year"),
        }
        for item in calendar
        if item.get("symbol") in WATCHLIST
    ]

    if filtered:
        print(f"   ✅ 关注列表内有盈利发布：{[e['symbol'] for e in filtered]}")
    else:
        print(f"   — 未来 {days} 天内关注列表无盈利发布")

    return filtered


# ─────────────────────────────────────────────
# 主入口
# ─────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="YMOS Finnhub 数据获取工具 — 市场新闻 + 个股行情 + 盈利日历"
    )
    parser.add_argument(
        "days",
        type=float,
        nargs="?",
        default=1,
        help="获取最近 N 天的新闻数据（默认: 1）",
    )
    parser.add_argument(
        "--output",
        default="financial_data.json",
        help="输出文件路径（默认: financial_data.json）",
    )
    parser.add_argument(
        "--no-quotes",
        action="store_true",
        help="跳过实时行情获取（节省 API 请求次数）",
    )
    parser.add_argument(
        "--no-earnings",
        action="store_true",
        help="跳过盈利日历获取",
    )

    args = parser.parse_args()

    print("=" * 55)
    print("YMOS Finnhub 数据获取工具")
    print(f"API 文档：https://finnhub.io/docs/api/")
    print("=" * 55)

    check_api_key()

    all_data = []

    # 1. 市场大盘新闻（/news）
    all_data.extend(fetch_market_news(args.days))

    # 2. 个股新闻（/company-news）
    print(f"\n🔍 获取个股新闻：{', '.join(WATCHLIST)}")
    for symbol in WATCHLIST:
        news = fetch_company_news(symbol, args.days)
        print(f"   [{symbol}] → {len(news)} 条")
        all_data.extend(news)

    # 3. 实时行情（/quote）
    if not args.no_quotes:
        all_data.extend(fetch_quotes(WATCHLIST))

    # 4. 盈利日历（/calendar/earnings）
    if not args.no_earnings:
        all_data.extend(fetch_earnings_calendar(days=7))

    # ── 输出结果 ──
    result = {
        "source": "Finnhub.io",
        "api_doc": "https://finnhub.io/docs/api/",
        "watchlist": WATCHLIST,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "time_range_days": args.days,
        "count": len(all_data),
        "data": all_data,
    }

    if all_data:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        news_count    = sum(1 for d in all_data if d["type"].endswith("news"))
        quote_count   = sum(1 for d in all_data if d["type"] == "quote")
        earning_count = sum(1 for d in all_data if d["type"] == "earnings")

        print(f"\n💾 数据已保存：{args.output}")
        print(f"✅ 新闻: {news_count} 条 | 行情: {quote_count} 支 | 盈利日历: {earning_count} 条")

    else:
        print("\n⚠️ 未获取到任何数据，请检查：")
        print("   1. API Key 是否正确（https://finnhub.io/dashboard）")
        print("   2. 网络是否可以访问 finnhub.io")
        print("   3. 是否超出免费额度（60次/分钟）")
        print()
        print("💡 也可以改用免费 RSS 方式（无需 API Key）：")
        print("   python3 scripts/fetch_rss.py 1 --output output.json")
        sys.exit(1)


if __name__ == "__main__":
    main()
