from __future__ import annotations

import json
import random
import re
import ssl
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

DEFAULT_SAMPLE_NEWS: List[Dict[str, Any]] = [
    {
        "title": "Cathie Wood says investors should consider rotating from gold into Bitcoin",
        "summary": "ARK Invest CEO Cathie Wood argued Bitcoin could outperform as investors review defensive allocations and long-term digital scarcity.",
        "url": "https://example.local/sample-cathie-wood-bitcoin",
        "source": "local_sample",
        "published_at": "2026-03-23T02:29:32+00:00",
        "image_url": "",
    },
    {
        "title": "Michael Saylor keeps calling Bitcoin a strategic long-term buy",
        "summary": "Strategy chairman Michael Saylor said long-term corporate buyers continue to accumulate Bitcoin on weakness.",
        "url": "https://example.local/sample-michael-saylor-bitcoin",
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

RSS_FEEDS: Tuple[Tuple[str, str], ...] = (
    ("google_news_crypto", "https://news.google.com/rss/search?{query}"),
    ("coindesk_rss", "https://www.coindesk.com/arc/outboundfeeds/rss/?outputType=xml"),
    ("cointelegraph_rss", "https://cointelegraph.com/rss"),
    ("decrypt_rss", "https://decrypt.co/feed"),
    ("bitcoin_magazine_rss", "https://bitcoinmagazine.com/.rss/full/"),
)

PUBLIC_HTML_SOURCES: Tuple[Tuple[str, str], ...] = (
    ("coindesk_markets", "https://www.coindesk.com/tag/bitcoin/"),
    ("decrypt_bitcoin", "https://decrypt.co/tags/bitcoin"),
    ("yahoo_finance_crypto", "https://finance.yahoo.com/topic/crypto/"),
)

BUY_KEYWORDS = (
    "buy bitcoin", "buy btc", "accumulate", "bullish", "says buy", "recommends buying", "backs bitcoin",
    "urges investors", "calls for buying", "strong buy", "long bitcoin", "gold to bitcoin", "rotate into bitcoin",
    "bitcoin is going higher", "price target", "institutional buying", "purchase bitcoin", "buy more bitcoin",
    "買え", "買い", "強気", "上昇予想", "蓄積", "投資推奨", "購入推奨", "btc買い増し", "ゴールドを売ってビットコインを買え",
)
PERSON_HINTS = (
    "cathie wood", "michael saylor", "larry fink", "samson mow", "mark yusko", "paul tudor jones",
    "brian armstrong", "changpeng zhao", "richard teng", "stan druckenmiller", "ray dalio", "jeremy allaire",
    "ceo", "founder", "chairman", "investor", "analyst", "strategist", "executive",
)
BTC_HINTS = ("bitcoin", "btc", "spot etf", "crypto", "digital asset", "institutional")
NEGATIVE_ONLY_HINTS = ("hack", "exploit", "breach", "stolen", "lawsuit only", "liquidation", "bankruptcy")
COINGECKO_BTC_URL = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd&include_24hr_change=true"


@dataclass
class FetchResult:
    article: Dict[str, Any]
    mode: str
    errors: List[str]
    article_count: int


class NewsFetcher:
    def __init__(self, timeout: int = 10, sample_path: str | Path | None = None, max_search_rounds: int = 4) -> None:
        self.timeout = timeout
        self.sample_path = Path(sample_path) if sample_path else None
        self.max_search_rounds = max_search_rounds
        self.random = random.Random(datetime.now(timezone.utc).strftime("%Y%m%d"))

    def fetch_latest(self) -> FetchResult:
        errors: List[str] = []
        attempts: List[Tuple[str, List[Dict[str, Any]]]] = []

        for mode, loader in (("rss", self._fetch_from_rss), ("scrape", self._fetch_from_html)):
            try:
                articles = loader(errors)
                if articles:
                    attempts.append((mode, articles))
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{mode}_failed: {exc}")

        for round_index in range(1, self.max_search_rounds + 1):
            for mode, articles in attempts:
                article = self._select_best_article(articles, require_person_buy=True, round_index=round_index)
                if article is not None:
                    article["market"] = self._fetch_market_data(errors, article)
                    return FetchResult(article=article, mode=mode, errors=errors, article_count=len(articles))
                errors.append(f"search_round_{round_index}: {mode} で人物付き買い推奨記事が見つかりませんでした")

        for mode, articles in attempts:
            article = self._select_best_article(articles, require_person_buy=False, round_index=1)
            if article is not None:
                article["market"] = self._fetch_market_data(errors, article)
                return FetchResult(article=article, mode=f"{mode}_fallback", errors=errors, article_count=len(articles))

        articles = self._load_local_sample()
        article = self._select_best_article(articles, require_person_buy=False, round_index=1) or articles[0]
        article["market"] = self._fetch_market_data(errors, article)
        return FetchResult(article=article, mode="sample", errors=errors, article_count=len(articles))

    def _fetch_from_rss(self, errors: List[str]) -> List[Dict[str, Any]]:
        aggregated: List[Dict[str, Any]] = []
        for source_name, feed_url in RSS_FEEDS:
            try:
                url = feed_url
                if "{query}" in feed_url:
                    query = urllib.parse.urlencode({
                        "q": 'bitcoin OR BTC OR crypto OR ETF OR Cathie Wood OR Michael Saylor when:7d',
                        "hl": "en-US",
                        "gl": "US",
                        "ceid": "US:en",
                    })
                    url = feed_url.format(query=query)
                root = self._read_xml(url)
                aggregated.extend(self._normalize_rss(source_name, root))
            except Exception as exc:  # noqa: BLE001
                errors.append(f"rss_source_failed:{source_name}:{exc}")
        normalized = self._dedupe_articles(aggregated)
        if not normalized:
            raise RuntimeError("no RSS articles available")
        return normalized

    def _fetch_from_html(self, errors: List[str]) -> List[Dict[str, Any]]:
        aggregated: List[Dict[str, Any]] = []
        for source_name, url in PUBLIC_HTML_SOURCES:
            try:
                html = self._read_text(url)
                aggregated.extend(self._normalize_html_listing(source_name, url, html))
            except Exception as exc:  # noqa: BLE001
                errors.append(f"html_source_failed:{source_name}:{exc}")
        normalized = self._dedupe_articles(aggregated)
        if not normalized:
            raise RuntimeError("no HTML articles available")
        return normalized

    def _select_best_article(self, articles: Iterable[Dict[str, Any]], require_person_buy: bool, round_index: int) -> Dict[str, Any] | None:
        candidates = []
        for article in self._dedupe_articles(list(articles)):
            score = self.score_article(article)
            if require_person_buy and not (score["person_score"] >= 1.0 and score["buy_signal_score"] >= 1.2 and score["btc_relevance_score"] >= 0.8):
                continue
            article = article.copy()
            article["selection_score"] = score
            candidates.append(article)
        if not candidates:
            return None
        ranked = sorted(candidates, key=lambda item: item["selection_score"]["total_score"], reverse=True)
        top_slice = ranked[: min(5, len(ranked))]
        weights = [max(0.05, item["selection_score"]["total_score"]) for item in top_slice]
        choice = self.random.choices(top_slice, weights=weights, k=1)[0]
        if round_index > 1 and len(top_slice) > 1:
            index = min(round_index - 1, len(top_slice) - 1)
            choice = top_slice[index]
        return choice

    def score_article(self, article: Dict[str, Any]) -> Dict[str, float]:
        text = f"{article.get('title', '')} {article.get('summary', '')}".lower()
        person_score = 0.0
        if any(hint in text for hint in PERSON_HINTS):
            person_score += 1.3
        if re.search(r"\b[A-Z][a-z]+\s+[A-Z][a-z]+\b", article.get("title", "")):
            person_score += 0.8
        buy_hits = sum(1 for keyword in BUY_KEYWORDS if keyword in text)
        buy_signal_score = min(2.4, 0.55 * buy_hits)
        btc_hits = sum(1 for keyword in BTC_HINTS if keyword in text)
        btc_relevance_score = min(2.0, 0.45 * btc_hits)
        if any(keyword in text for keyword in NEGATIVE_ONLY_HINTS) and buy_hits == 0:
            buy_signal_score = max(0.0, buy_signal_score - 0.8)
        freshness_score = self._freshness_score(article.get("published_at", ""))
        total_score = round(person_score + buy_signal_score + btc_relevance_score + freshness_score, 4)
        return {
            "person_score": round(person_score, 4),
            "buy_signal_score": round(buy_signal_score, 4),
            "btc_relevance_score": round(btc_relevance_score, 4),
            "freshness_score": round(freshness_score, 4),
            "total_score": total_score,
        }

    def _freshness_score(self, published_at: str) -> float:
        try:
            stamp = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
            age_hours = max(0.0, (datetime.now(timezone.utc) - stamp.astimezone(timezone.utc)).total_seconds() / 3600)
            if age_hours <= 24:
                return 1.0
            if age_hours <= 72:
                return 0.7
            if age_hours <= 168:
                return 0.4
            return 0.1
        except Exception:  # noqa: BLE001
            return 0.2

    def _normalize_rss(self, source_name: str, root: ET.Element) -> List[Dict[str, Any]]:
        channel = root.find("channel")
        items = channel.findall("item") if channel is not None else root.findall(".//item")
        results: List[Dict[str, Any]] = []
        for item in items[:40]:
            title = self._clean_html(item.findtext("title") or "")
            summary = self._clean_html(item.findtext("description") or item.findtext("summary") or "")
            url = (item.findtext("link") or "").strip()
            pub_date = (item.findtext("pubDate") or item.findtext("published") or "").strip()
            canonical = {
                "title": title,
                "summary": summary,
                "url": url,
                "source": source_name,
                "published_at": self._parse_published_at(pub_date),
                "image_url": self._extract_media_url(item),
            }
            if self._valid_article(canonical):
                results.append(canonical)
        return results

    def _normalize_html_listing(self, source_name: str, base_url: str, html: str) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        seen: set[str] = set()
        for href, title in re.findall(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', html, flags=re.IGNORECASE | re.DOTALL):
            clean_title = self._clean_html(title)
            if len(clean_title) < 30:
                continue
            absolute = urllib.parse.urljoin(base_url, href.strip())
            key = absolute.lower()
            if key in seen:
                continue
            seen.add(key)
            if not any(token in clean_title.lower() for token in ("bitcoin", "btc", "crypto", "etf")):
                continue
            results.append(
                {
                    "title": clean_title,
                    "summary": clean_title,
                    "url": absolute,
                    "source": source_name,
                    "published_at": self._now_iso(),
                    "image_url": "",
                }
            )
            if len(results) >= 25:
                break
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

    def _read_text(self, url: str) -> str:
        with urllib.request.urlopen(self._build_request(url), timeout=self.timeout, context=self._ssl_context()) as response:
            return response.read().decode("utf-8", errors="ignore")

    @staticmethod
    def _build_request(url: str) -> urllib.request.Request:
        return urllib.request.Request(url, headers={"User-Agent": "inst_auto/2.0"})

    @staticmethod
    def _ssl_context() -> ssl.SSLContext:
        return ssl.create_default_context()

    @staticmethod
    def _clean_html(text: str) -> str:
        cleaned = re.sub(r"<[^>]+>", " ", unescape(text or ""))
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned

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
