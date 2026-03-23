from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from typing import Any, Dict, List

from normalizers import compact_whitespace, normalize_coin_mentions, normalize_organizations, normalize_people

DEFAULT_EXTRACTION = {
    "topic": "仮想通貨ニュース",
    "summary_ja": "",
    "people": [],
    "organizations": [],
    "coins": [],
    "sentiment": "neutral",
    "market_impact": "medium",
    "claim_summary": "",
    "image_hint": "",
    "is_crypto_related": True,
}

ORG_CANDIDATES = [
    "BlackRock", "Grayscale", "Coinbase", "Binance", "ARK Invest", "SEC", "Federal Reserve", "FOMC",
    "Metaplanet", "Strategy", "MicroStrategy", "Tether", "Circle", "Fidelity", "Nasdaq",
]

PERSON_ROLE_MAP = {
    "Cathie Wood": "ARK Invest CEO",
    "Larry Fink": "BlackRock CEO",
    "Brian Armstrong": "Coinbase CEO",
    "Richard Teng": "Binance CEO",
    "Changpeng Zhao": "Binance Founder",
    "Michael Saylor": "Strategy Executive Chairman",
    "Paolo Ardoino": "Tether CEO",
    "Jeremy Allaire": "Circle CEO",
    "Vitalik Buterin": "Ethereum Co-Founder",
    "Brad Garlinghouse": "Ripple CEO",
    "Anatoly Yakovenko": "Solana Co-Founder",
}


class AIExtractor:
    def __init__(self, timeout: int = 20) -> None:
        self.timeout = timeout

    def extract(self, article: Dict[str, Any]) -> Dict[str, Any]:
        gpt_payload: Dict[str, Any] | None = None
        try:
            gpt_payload = self._extract_with_openai(article)
        except Exception:  # noqa: BLE001
            gpt_payload = None

        fallback = self._rule_based_extract(article)
        merged = self._merge_and_normalize(article, gpt_payload or {}, fallback)
        return json.loads(json.dumps(merged, ensure_ascii=False))

    def _extract_with_openai(self, article: Dict[str, Any]) -> Dict[str, Any] | None:
        api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
        if not api_key:
            return None
        model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
        body = {
            "model": model,
            "input": [
                {
                    "role": "system",
                    "content": [
                        {
                            "type": "input_text",
                            "text": (
                                "You extract structured crypto-news metadata. "
                                "Return JSON only. Follow this schema exactly: "
                                "{topic, summary_ja, people, organizations, coins, sentiment, market_impact, claim_summary, image_hint, is_crypto_related}. "
                                "Rules: people must contain only real persons explicitly mentioned in the article. "
                                "Do not put companies, organizations, ETFs, coins, countries, laws, or products into people. "
                                "Organizations are companies, regulators, funds, or institutions. "
                                "Coins must be crypto tickers if explicitly mentioned. "
                                "Do not invent facts. Unknown values must be empty string or empty arrays. JSON only."
                            ),
                        }
                    ],
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": json.dumps(
                                {
                                    "title": article.get("title", ""),
                                    "summary": article.get("summary", ""),
                                    "source": article.get("source", ""),
                                    "published_at": article.get("published_at", ""),
                                    "market": article.get("market", {}),
                                },
                                ensure_ascii=False,
                            ),
                        }
                    ],
                },
            ],
            "text": {"format": {"type": "json_object"}},
        }
        for _ in range(2):
            try:
                payload = self._post_json("https://api.openai.com/v1/responses", body, api_key)
                text = self._extract_response_text(payload)
                if not text:
                    continue
                data = json.loads(text)
                if isinstance(data, dict):
                    return data
            except Exception:  # noqa: BLE001
                continue
        return None

    def _rule_based_extract(self, article: Dict[str, Any]) -> Dict[str, Any]:
        text = compact_whitespace(f"{article.get('title', '')} {article.get('summary', '')}")
        organizations = self._detect_organizations(text)
        raw_people = self._detect_people(text)
        coins = normalize_coin_mentions(raw_people + organizations + [text], text)
        people = normalize_people(raw_people, organizations=organizations, text=text)
        sentiment = self._detect_sentiment(text, article.get("market", {}))
        market_impact = self._detect_market_impact(text, article.get("market", {}))
        summary_ja = self._build_summary_ja(article, people, organizations, coins)
        claim_summary = self._build_claim_summary(article)
        topic = self._pick_topic(article, coins, organizations)
        return {
            "topic": topic,
            "summary_ja": summary_ja,
            "people": people,
            "organizations": organizations,
            "coins": coins,
            "sentiment": sentiment,
            "market_impact": market_impact,
            "claim_summary": claim_summary,
            "image_hint": self._build_image_hint(topic, people, coins, sentiment),
            "is_crypto_related": self._is_crypto_related(text, coins, organizations),
        }

    def _merge_and_normalize(self, article: Dict[str, Any], gpt_payload: Dict[str, Any], fallback: Dict[str, Any]) -> Dict[str, Any]:
        merged = {**DEFAULT_EXTRACTION, **fallback, **{k: v for k, v in gpt_payload.items() if v not in (None, "", [], {})}}
        text = compact_whitespace(f"{article.get('title', '')} {article.get('summary', '')}")
        organizations = normalize_organizations(merged.get("organizations") or fallback.get("organizations") or self._detect_organizations(text))
        people = normalize_people(merged.get("people") or fallback.get("people") or [], organizations=organizations, text=text)
        coins = normalize_coin_mentions(merged.get("coins") or fallback.get("coins") or [], text=text)
        merged.update(
            {
                "topic": compact_whitespace(merged.get("topic") or fallback.get("topic") or "仮想通貨ニュース"),
                "summary_ja": compact_whitespace(merged.get("summary_ja") or fallback.get("summary_ja") or self._build_summary_ja(article, people, organizations, coins)),
                "people": people,
                "organizations": organizations,
                "coins": coins,
                "sentiment": self._normalize_sentiment(merged.get("sentiment") or fallback.get("sentiment")),
                "market_impact": self._normalize_market_impact(merged.get("market_impact") or fallback.get("market_impact")),
                "claim_summary": compact_whitespace(merged.get("claim_summary") or fallback.get("claim_summary") or self._build_claim_summary(article)),
                "image_hint": compact_whitespace(merged.get("image_hint") or fallback.get("image_hint") or self._build_image_hint(merged.get("topic", "仮想通貨ニュース"), people, coins, merged.get("sentiment", "neutral"))),
                "is_crypto_related": bool(merged.get("is_crypto_related", fallback.get("is_crypto_related", True))),
            }
        )
        person = self._build_person_profile(article, people, organizations, coins)
        merged.update(
            {
                "headline": compact_whitespace(article.get("title", ""))[:96],
                "person": person,
                "article_title": article.get("title", ""),
                "article_summary": article.get("summary", ""),
                "market": article.get("market", {}),
            }
        )
        return merged

    def _detect_people(self, text: str) -> List[str]:
        matches = re.findall(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})\b", text)
        deduped: List[str] = []
        for match in matches:
            if match not in deduped:
                deduped.append(match)
        return deduped

    def _detect_organizations(self, text: str) -> List[str]:
        found = [org for org in ORG_CANDIDATES if org.lower() in text.lower()]
        return found[:6]

    def _build_person_profile(self, article: Dict[str, Any], people: List[str], organizations: List[str], coins: List[str]) -> Dict[str, str]:
        if people:
            name = people[0]
            role = PERSON_ROLE_MAP.get(name) or (organizations[0] if organizations else "Crypto market commentator")
            summary = compact_whitespace(article.get("summary") or article.get("title") or "")[:84]
            return {"name": name, "role": role, "summary": summary, "avatar_mode": "person"}
        coin_hint = coins[0] if coins else "BTC"
        return {
            "name": "Market Watch",
            "role": "Fallback Avatar",
            "summary": f"人物が特定できないため、{coin_hint} を軸に市場イメージを表示します。",
            "avatar_mode": "fallback",
        }

    def _pick_topic(self, article: Dict[str, Any], coins: List[str], organizations: List[str]) -> str:
        title = (article.get("title") or "").lower()
        if coins:
            return f"{coins[0]}関連ニュース"
        if "etf" in title:
            return "ETF関連ニュース"
        if any(org in organizations for org in ("SEC", "Federal Reserve", "FOMC")):
            return "規制関連ニュース"
        return "仮想通貨ニュース"

    def _build_summary_ja(self, article: Dict[str, Any], people: List[str], organizations: List[str], coins: List[str]) -> str:
        subject = people[0] if people else organizations[0] if organizations else (coins[0] if coins else "仮想通貨市場")
        base = compact_whitespace(article.get("summary") or article.get("title") or "")
        return f"{subject}に関する報道です。{base[:110]}"

    def _build_claim_summary(self, article: Dict[str, Any]) -> str:
        return compact_whitespace(article.get("summary") or article.get("title") or "")[:120]

    def _build_image_hint(self, topic: str, people: List[str], coins: List[str], sentiment: str) -> str:
        subject = people[0] if people else (coins[0] if coins else "BTC")
        mood = {"positive": "強気", "negative": "警戒", "neutral": "注目"}.get(sentiment, "注目")
        return f"人物左・コイン右のニュースカード。主題は{subject}。全体トーンは{mood}。topic={topic}"

    def _detect_sentiment(self, text: str, market: Dict[str, Any]) -> str:
        lowered = text.lower()
        positive_markers = ["gain", "rise", "surge", "inflow", "approve", "adoption", "record"]
        negative_markers = ["drop", "fall", "lawsuit", "outflow", "risk", "concern", "sell", "decline"]
        pos = sum(1 for marker in positive_markers if marker in lowered)
        neg = sum(1 for marker in negative_markers if marker in lowered)
        change = float(market.get("btc_change_percent", 0.0) or 0.0)
        if change > 1.0:
            pos += 1
        elif change < -1.0:
            neg += 1
        if pos > neg:
            return "positive"
        if neg > pos:
            return "negative"
        return "neutral"

    def _detect_market_impact(self, text: str, market: Dict[str, Any]) -> str:
        lowered = text.lower()
        if any(keyword in lowered for keyword in ("etf", "sec", "fed", "lawsuit", "approval", "liquidation")):
            return "high"
        if abs(float(market.get("btc_change_percent", 0.0) or 0.0)) >= 2.0:
            return "high"
        if any(keyword in lowered for keyword in ("bitcoin", "ethereum", "solana", "xrp")):
            return "medium"
        return "low"

    def _is_crypto_related(self, text: str, coins: List[str], organizations: List[str]) -> bool:
        lowered = text.lower()
        return bool(coins or any(word in lowered for word in ("crypto", "bitcoin", "ethereum", "blockchain", "etf")) or organizations)

    @staticmethod
    def _normalize_sentiment(value: str) -> str:
        return value if value in {"positive", "neutral", "negative"} else "neutral"

    @staticmethod
    def _normalize_market_impact(value: str) -> str:
        return value if value in {"high", "medium", "low"} else "medium"

    @staticmethod
    def _post_json(url: str, body: Dict[str, Any], api_key: str) -> Dict[str, Any]:
        request = urllib.request.Request(
            url,
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))

    @staticmethod
    def _extract_response_text(payload: Dict[str, Any]) -> str:
        if isinstance(payload.get("output_text"), str):
            return payload["output_text"]
        chunks: List[str] = []
        for item in payload.get("output", []):
            for content in item.get("content", []):
                text = content.get("text")
                if isinstance(text, str):
                    chunks.append(text)
        return "".join(chunks).strip()
