from __future__ import annotations

import json
import os
import ssl
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

DEFAULT_SAMPLE_NEWS: List[Dict[str, Any]] = [
    {
        "title": "Cathie Wood says Bitcoin could benefit if investors rotate out of gold",
        "summary": "ARK Invest's Cathie Wood said Bitcoin may continue gaining attention as institutions reassess gold allocations.",
        "url": "https://example.local/sample-cathie-wood-bitcoin",
        "source": "local_sample",
        "published_at": "2026-03-23T02:29:32+00:00",
        "image_url": "",
    },
    {
        "title": "US spot Bitcoin ETF flows remain a key market focus",
        "summary": "ETF flow data and regulation headlines continue to shape near-term crypto sentiment.",
        "url": "https://example.local/sample-bitcoin-etf",
        "source": "local_sample",
        "published_at": "2026-03-22T08:15:00+00:00",
        "image_url": "",
    },
]

DEFAULT_MARKET_SAMPLES: List[Dict[str, Any]] = [
    {"btc_price": 68214.05, "btc_change_percent": -1.6, "btc_direction": "down"},
    {"btc_price": 70488.12, "btc_change_percent": 2.4, "btc_direction": "up"},
    {"btc_price": 69105.44, "btc_change_percent": 0.2, "btc_direction": "neutral"},
]

CRYPTO_PANIC_URL = "https://cryptopanic.com/api/free/v1/posts/?kind=news&currencies=BTC,ETH,SOL,XRP&page=1"
NEWSAPI_URL = "https://newsapi.org/v2/everything?{query}"
RSS_FEEDS: Tuple[Tuple[str, str], ...] = (
    ("google_news_crypto", "https://news.google.com/rss/search?{query}"),
    ("cointelegraph_rss", "https://cointelegraph.com/rss"),
    ("coindesk_rss", "https://www.coindesk.com/arc/outboundfeeds/rss/"),
)
COINGECKO_BTC_URL = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd&include_24hr_change=true"
CRYPTO_KEYWORDS = ("bitcoin", "btc", "ethereum", "eth", "crypto", "cryptocurrency", "etf", "solana", "xrp", "regulation", "sec")


@dataclass
class FetchResult:
    article: Dict[str, Any]
    mode: str
    errors: List[str]
    article_count: int


class NewsFetcher:
    def __init__(self, timeout: int = 10, sample_path: str | Path | None = None) -> None:
        self.timeout = timeout
        self.sample_path = Path(sample_path) if sample_path else None

    def fetch_latest(self) -> FetchResult:
        errors: List[str] = []

        for mode, loader in (("api", self._fetch_from_api), ("rss", self._fetch_from_rss)):
            try:
                articles = loader(errors)
                article = self._select_best_article(articles)
                article["market"] = self._fetch_market_data(errors, article)
                return FetchResult(article=article, mode=mode, errors=errors, article_count=len(articles))
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{mode}_failed: {exc}")

        articles = self._load_local_sample()
        article = self._select_best_article(articles)
        article["market"] = self._fetch_market_data(errors, article)
        return FetchResult(article=article, mode="sample", errors=errors, article_count=len(articles))

    def _fetch_from_api(self, errors: List[str]) -> List[Dict[str, Any]]:
        aggregated: List[Dict[str, Any]] = []
        cryptopanic_token = os.getenv("CRYPTOPANIC_API_TOKEN", "").strip()
        if cryptopanic_token:
            url = f"{CRYPTO_PANIC_URL}&auth_token={urllib.parse.quote(cryptopanic_token)}"
            payload = self._read_json(url)
            aggregated.extend(self._normalize_cryptopanic(payload))
        else:
            errors.append("api_skipped: CRYPTOPANIC_API_TOKEN not set")

        newsapi_key = os.getenv("NEWSAPI_API_KEY") or os.getenv("NEWS_API_KEY") or ""
        if newsapi_key:
            query = urllib.parse.urlencode({
                "q": '("bitcoin" OR "crypto" OR "ethereum" OR "spot ETF" OR "SEC" OR "solana")',
                "language": "en",
                "sortBy": "publishedAt",
                "pageSize": 20,
                "apiKey": newsapi_key,
            })
            payload = self._read_json(NEWSAPI_URL.format(query=query))
            aggregated.extend(self._normalize_newsapi(payload))
        else:
            errors.append("api_skipped: NEWSAPI_API_KEY not set")

        normalized = self._dedupe_articles(aggregated)
        if not normalized:
            raise RuntimeError("no API articles available")
        return normalized

    def _fetch_from_rss(self, errors: List[str]) -> List[Dict[str, Any]]:
        aggregated: List[Dict[str, Any]] = []
        for source_name, feed_url in RSS_FEEDS:
            try:
                if "{query}" in feed_url:
                    query = urllib.parse.urlencode({"q": "cryptocurrency OR bitcoin OR ethereum OR ETF when:7d", "hl": "en-US", "gl": "US", "ceid": "US:en"})
                    root = self._read_xml(feed_url.format(query=query))
                else:
                    root = self._read_xml(feed_url)
                aggregated.extend(self._normalize_rss(source_name, root))
            except Exception as exc:  # noqa: BLE001
                errors.append(f"rss_source_failed:{source_name}:{exc}")
        normalized = self._dedupe_articles(aggregated)
        if not normalized:
            raise RuntimeError("no RSS articles available")
        return normalized

    def _select_best_article(self, articles: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
        candidates = self._dedupe_articles(list(articles))
        if not candidates:
            raise RuntimeError("no candidate article")
        ranked = sorted(candidates, key=self._article_rank, reverse=True)
        return ranked[0]

    def _article_rank(self, article: Dict[str, Any]) -> Tuple[float, str]:
        text = f"{article.get('title', '')} {article.get('summary', '')}".lower()
        score = sum(1.0 for keyword in CRYPTO_KEYWORDS if keyword in text)
        if any(name in text for name in ("blackrock", "larry fink", "cathie wood", "saylor", "sec", "etf")):
            score += 1.5
        return score, article.get("published_at", "")

    def _normalize_cryptopanic(self, payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        for item in payload.get("results") or []:
            metadata = item.get("metadata") or {}
            source = item.get("source") or {}
            canonical = {
                "title": item.get("title") or "",
                "summary": metadata.get("description") or item.get("slug") or "",
                "url": item.get("url") or "",
                "source": source.get("title") or "cryptopanic",
                "published_at": item.get("published_at") or self._now_iso(),
                "image_url": item.get("image") or metadata.get("image") or "",
            }
            if self._valid_article(canonical):
                results.append(canonical)
        return results

    def _normalize_newsapi(self, payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        for item in payload.get("articles") or []:
            canonical = {
                "title": item.get("title") or "",
                "summary": item.get("description") or item.get("content") or "",
                "url": item.get("url") or "",
                "source": (item.get("source") or {}).get("name") or "newsapi",
                "published_at": item.get("publishedAt") or self._now_iso(),
                "image_url": item.get("urlToImage") or "",
            }
            if self._valid_article(canonical):
                results.append(canonical)
        return results

    def _normalize_rss(self, source_name: str, root: ET.Element) -> List[Dict[str, Any]]:
        channel = root.find("channel")
        items = channel.findall("item") if channel is not None else root.findall(".//item")
        results: List[Dict[str, Any]] = []
        for item in items[:30]:
            title = (item.findtext("title") or "").strip()
            summary = (item.findtext("description") or item.findtext("summary") or "").strip()
            url = (item.findtext("link") or "").strip()
            pub_date = (item.findtext("pubDate") or item.findtext("published") or "").strip()
            published_at = self._parse_published_at(pub_date)
            canonical = {
                "title": title,
                "summary": summary,
                "url": url,
                "source": source_name,
                "published_at": published_at,
                "image_url": self._extract_media_url(item),
            }
            if self._valid_article(canonical):
                results.append(canonical)
        return results

    def _fetch_market_data(self, errors: List[str], article: Dict[str, Any]) -> Dict[str, Any]:
        try:
            payload = self._read_json(COINGECKO_BTC_URL)
            btc = payload.get("bitcoin") or {}
            price = round(float(btc.get("usd")), 2)
            change = round(float(btc.get("usd_24h_change")), 2)
            return {"btc_price": price, "btc_change_percent": change, "btc_direction": self._direction_from_change(change)}
        except Exception as exc:  # noqa: BLE001
            errors.append(f"market_failed: {exc}")
            return self._fallback_market(article)

    def _fallback_market(self, article: Dict[str, Any]) -> Dict[str, Any]:
        published = article.get("published_at") or self._now_iso()
        try:
            stamp = datetime.fromisoformat(published.replace("Z", "+00:00"))
            index = stamp.toordinal() % len(DEFAULT_MARKET_SAMPLES)
        except ValueError:
            index = 0
        return DEFAULT_MARKET_SAMPLES[index].copy()

    def _load_local_sample(self) -> List[Dict[str, Any]]:
        if self.sample_path and self.sample_path.exists():
            with self.sample_path.open("r", encoding="utf-8") as fp:
                data = json.load(fp)
            if isinstance(data, list) and data:
                return [self._coerce_article(item) for item in data if isinstance(item, dict)]
            if isinstance(data, dict):
                return [self._coerce_article(data)]
        return [article.copy() for article in DEFAULT_SAMPLE_NEWS]

    def _coerce_article(self, article: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "title": article.get("title") or "",
            "summary": article.get("summary") or article.get("description") or "",
            "url": article.get("url") or "",
            "source": article.get("source") or "local_sample",
            "published_at": article.get("published_at") or self._now_iso(),
            "image_url": article.get("image_url") or article.get("urlToImage") or "",
        }

    def _dedupe_articles(self, articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        deduped: Dict[str, Dict[str, Any]] = {}
        for article in articles:
            article = self._coerce_article(article)
            if not self._valid_article(article):
                continue
            key = (article["url"] or article["title"]).strip().lower()
            existing = deduped.get(key)
            if existing is None or article.get("published_at", "") > existing.get("published_at", ""):
                deduped[key] = article
        return sorted(deduped.values(), key=lambda item: item.get("published_at", ""), reverse=True)

    def _valid_article(self, article: Dict[str, Any]) -> bool:
        return bool((article.get("title") or "").strip() and (article.get("url") or "").strip())

    def _extract_media_url(self, item: ET.Element) -> str:
        for tag_name in ("{http://search.yahoo.com/mrss/}content", "{http://search.yahoo.com/mrss/}thumbnail"):
            media = item.find(tag_name)
            if media is not None and media.attrib.get("url"):
                return media.attrib["url"]
        enclosure = item.find("enclosure")
        if enclosure is not None and enclosure.attrib.get("url"):
            return enclosure.attrib["url"]
        return ""

    def _read_json(self, url: str) -> Dict[str, Any]:
        with urllib.request.urlopen(self._build_request(url), timeout=self.timeout, context=self._ssl_context()) as response:
            return json.loads(response.read().decode("utf-8"))

    def _read_xml(self, url: str) -> ET.Element:
        with urllib.request.urlopen(self._build_request(url), timeout=self.timeout, context=self._ssl_context()) as response:
            return ET.fromstring(response.read())

    @staticmethod
    def _build_request(url: str) -> urllib.request.Request:
        return urllib.request.Request(url, headers={"User-Agent": "inst_auto/2.0"})

    @staticmethod
    def _ssl_context() -> ssl.SSLContext:
        return ssl.create_default_context()

    @staticmethod
    def _parse_published_at(value: str) -> str:
        if not value:
            return datetime.now(timezone.utc).isoformat()
        try:
            return parsedate_to_datetime(value).astimezone(timezone.utc).isoformat()
        except Exception:  # noqa: BLE001
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc).isoformat()
            except Exception:  # noqa: BLE001
                return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _direction_from_change(change: float) -> str:
        if change > 0.3:
            return "up"
        if change < -0.3:
            return "down"
        return "neutral"
