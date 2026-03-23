from __future__ import annotations

import json
import os
import ssl
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


DEFAULT_SAMPLE_NEWS: List[Dict[str, Any]] = [
    {
        "title": "Bitcoin ETF flows remain in focus as institutions watch macro signals",
        "summary": "Analysts say Bitcoin exchange-traded fund flows and broader macro signals remain key drivers for short-term sentiment in the crypto market.",
        "url": "https://example.local/sample-bitcoin-etf",
        "published_at": "2026-01-15T09:00:00+00:00",
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
                return data[0]
            if isinstance(data, dict):
                return data
        return DEFAULT_SAMPLE_NEWS[0].copy()

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
