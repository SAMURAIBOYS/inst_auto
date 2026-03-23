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
from typing import Any, Dict, List

DEFAULT_SAMPLE_NEWS: List[Dict[str, Any]] = [
    {
        "title": "Cathie Wood urges investors to sell gold for Bitcoin, says BTC will hit $1,500,000",
        "summary": "Cathie Wood says investors should move from gold into Bitcoin and argues BTC could eventually reach 1.5 million dollars as institutional adoption expands.",
        "url": "https://example.local/sample-cathie-wood-bitcoin",
        "published_at": "2026-03-23T02:29:32+00:00",
        "source": "local_sample",
    },
    {
        "title": "Ethereum ecosystem builders highlight scaling and stablecoin demand",
        "summary": "Developers and market observers continue to point to layer-2 adoption and stablecoin usage as major themes for Ethereum-related coverage.",
        "url": "https://example.local/sample-ethereum",
        "published_at": "2026-01-14T08:00:00+00:00",
        "source": "local_sample",
    },
]

CRYPTO_PANIC_URL = "https://cryptopanic.com/api/v1/posts/?public=true&kind=news&currencies=BTC,ETH,SOL,XRP"
GOOGLE_NEWS_RSS = "https://news.google.com/rss/search?{query}"
COINGECKO_BTC_URL = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd&include_24hr_change=true"


@dataclass
class FetchResult:
    article: Dict[str, Any]
    mode: str
    errors: List[str]


class NewsFetcher:
    def __init__(self, timeout: int = 10, sample_path: str | Path | None = None) -> None:
        self.timeout = timeout
        self.sample_path = Path(sample_path) if sample_path else None

    def fetch_latest(self) -> FetchResult:
        errors: List[str] = []

        try:
            article = self._fetch_from_api()
            return FetchResult(article=article, mode="api", errors=errors)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"api_failed: {exc}")

        try:
            article = self._fetch_from_rss()
            return FetchResult(article=article, mode="rss", errors=errors)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"rss_failed: {exc}")

        article = self._load_local_sample()
        return FetchResult(article=article, mode="sample", errors=errors)

    def fetch_market(self) -> Dict[str, Any]:
        errors: List[str] = []
        try:
            payload = self._read_json(COINGECKO_BTC_URL)
            btc = payload.get("bitcoin") or {}
            price = float(btc.get("usd"))
            change = float(btc.get("usd_24h_change"))
            return {
                "btc_price": round(price, 2),
                "btc_change_percent": round(change, 2),
                "btc_direction": self._direction(change),
                "source": "api:coingecko",
                "errors": errors,
            }
        except Exception as exc:  # noqa: BLE001
            errors.append(f"market_api_failed: {exc}")
            sample = self._sample_market()
            sample["errors"] = errors
            return sample

    def _fetch_from_api(self) -> Dict[str, Any]:
        token = os.getenv("CRYPTOPANIC_API_TOKEN") or os.getenv("NEWS_API_TOKEN")
        request_url = CRYPTO_PANIC_URL
        if token:
            request_url += "&auth_token=" + urllib.parse.quote(token)

        payload = self._read_json(request_url)
        items = payload.get("results") or []
        if not items:
            raise RuntimeError("no API results")

        ranked = sorted(items, key=lambda item: item.get("published_at") or "", reverse=True)
        item = ranked[0]
        return {
            "title": item.get("title", "Untitled crypto news"),
            "summary": item.get("metadata", {}).get("description") or item.get("slug", ""),
            "url": item.get("url") or item.get("domain", ""),
            "published_at": item.get("published_at") or self._now_iso(),
            "source": f"api:{item.get('source', {}).get('title', 'cryptopanic')}",
        }

    def _fetch_from_rss(self) -> Dict[str, Any]:
        query = urllib.parse.urlencode({"q": "cryptocurrency OR bitcoin OR ethereum when:7d", "hl": "en-US", "gl": "US", "ceid": "US:en"})
        root = self._read_xml(GOOGLE_NEWS_RSS.format(query=query))
        channel = root.find("channel")
        if channel is None:
            raise RuntimeError("RSS channel missing")
        item = channel.find("item")
        if item is None:
            raise RuntimeError("RSS item missing")

        pub_date = item.findtext("pubDate")
        published_at = self._now_iso()
        if pub_date:
            try:
                published_at = parsedate_to_datetime(pub_date).astimezone(timezone.utc).isoformat()
            except Exception:  # noqa: BLE001
                published_at = self._now_iso()

        return {
            "title": item.findtext("title", default="Untitled crypto news"),
            "summary": item.findtext("description", default=""),
            "url": item.findtext("link", default=""),
            "published_at": published_at,
            "source": "rss:google_news",
        }

    def _load_local_sample(self) -> Dict[str, Any]:
        if self.sample_path and self.sample_path.exists():
            with self.sample_path.open("r", encoding="utf-8") as fp:
                data = json.load(fp)
            if isinstance(data, list) and data:
                day_index = datetime.now(timezone.utc).timetuple().tm_yday % len(data)
                return data[day_index]
            if isinstance(data, dict):
                return data
        day_index = datetime.now(timezone.utc).timetuple().tm_yday % len(DEFAULT_SAMPLE_NEWS)
        return DEFAULT_SAMPLE_NEWS[day_index].copy()

    def _sample_market(self) -> Dict[str, Any]:
        today = datetime.now(timezone.utc)
        day_seed = today.year * 1000 + today.timetuple().tm_yday
        price = 62000 + (day_seed % 9000) + ((day_seed % 100) / 100)
        change = ((day_seed % 17) - 8) * 0.7
        return {
            "btc_price": round(price, 2),
            "btc_change_percent": round(change, 2),
            "btc_direction": self._direction(change),
            "source": "sample:daily_market",
        }

    def _read_json(self, url: str) -> Dict[str, Any]:
        with urllib.request.urlopen(self._build_request(url), timeout=self.timeout, context=self._ssl_context()) as response:
            return json.loads(response.read().decode("utf-8"))

    def _read_xml(self, url: str) -> ET.Element:
        with urllib.request.urlopen(self._build_request(url), timeout=self.timeout, context=self._ssl_context()) as response:
            return ET.fromstring(response.read())

    @staticmethod
    def _build_request(url: str) -> urllib.request.Request:
        return urllib.request.Request(url, headers={"User-Agent": "inst_auto/1.0"})

    @staticmethod
    def _ssl_context() -> ssl.SSLContext:
        return ssl.create_default_context()

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _direction(change: float) -> str:
        if change > 0.2:
            return "bullish"
        if change < -0.2:
            return "bearish"
        return "neutral"
