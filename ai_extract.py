from __future__ import annotations

import json
import os
import re
import urllib.request
from typing import Any, Dict, List

from normalizers import compact_whitespace, is_probable_person_name, normalize_coin_mentions, normalize_organizations, normalize_people

DEFAULT_EXTRACTION = {
    "headline_ja": "",
    "topic": "仮想通貨ニュース",
    "summary_ja": "",
    "person_name": "",
    "person_role": "",
    "organization": "",
    "coins": [],
    "sentiment": "neutral",
    "market_impact": "medium",
    "buy_signal": False,
    "buy_reason": "",
    "claim_summary": "",
    "image_hint": "",
    "is_crypto_related": True,
}

ORG_CANDIDATES = [
    "BlackRock", "Grayscale", "Coinbase", "Binance", "ARK Invest", "SEC", "Federal Reserve", "FOMC",
    "Metaplanet", "Strategy", "MicroStrategy", "Tether", "Circle", "Fidelity", "Nasdaq", "Yahoo Finance",
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
BUY_MARKERS = [
    "buy bitcoin", "buy btc", "accumulate", "bullish", "recommends buying", "backs bitcoin", "urges investors",
    "calls for buying", "long bitcoin", "gold to bitcoin", "rotate into bitcoin", "going higher", "price target",
    "institutional buying", "買い", "強気", "蓄積", "購入推奨", "投資推奨", "買い増し",
]


class AIExtractor:
    def __init__(self, timeout: int = 20) -> None:
        self.timeout = timeout

    def extract(self, article: Dict[str, Any]) -> Dict[str, Any]:
        gpt_payload: Dict[str, Any] | None = None
        try:
            gpt_payload = self._extract_with_openai(article)
        except Exception:
            gpt_payload = None
        fallback = self._rule_based_extract(article)
        merged = self._merge_and_normalize(article, gpt_payload or {}, fallback)
        return json.loads(json.dumps(merged, ensure_ascii=False))

    def _extract_with_openai(self, article: Dict[str, Any]) -> Dict[str, Any] | None:
        api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
        if not api_key:
            return None
        model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
        schema = {
            "headline_ja": "",
            "topic": "",
            "summary_ja": "",
            "person_name": "",
            "person_role": "",
            "organization": "",
            "coins": [],
            "sentiment": "positive|neutral|negative",
            "market_impact": "high|medium|low",
            "buy_signal": True,
            "buy_reason": "",
            "claim_summary": "",
            "image_hint": "",
            "is_crypto_related": True,
        }
        body = {
            "model": model,
            "input": [
                {
                    "role": "system",
                    "content": [{
                        "type": "input_text",
                        "text": (
                            "You extract structured crypto-news metadata. Return JSON only. "
                            f"Schema: {json.dumps(schema, ensure_ascii=False)}. "
                            "Rules: person_name must be a real person explicitly stated in the article. "
                            "Never put Bitcoin, BTC, SEC, ETFs, companies, countries, institutions, products, or coins into person_name. "
                            "organization must contain only one main company/regulator if present. "
                            "coins must be tickers explicitly mentioned. "
                            "buy_signal should be true only if the article explicitly indicates buying, accumulation, bullish recommendation, or rotating into Bitcoin. "
                            "Do not invent facts. Unknown values must be empty strings or empty arrays. JSON only."
                        ),
                    }],
                },
                {
                    "role": "user",
                    "content": [{
                        "type": "input_text",
                        "text": json.dumps({
                            "title": article.get("title", ""),
                            "summary": article.get("summary", ""),
                            "source": article.get("source", ""),
                            "published_at": article.get("published_at", ""),
                            "market": article.get("market", {}),
                        }, ensure_ascii=False),
                    }],
                },
            ],
            "text": {"format": {"type": "json_object"}},
        }
        req = urllib.request.Request(
            "https://api.openai.com/v1/responses",
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
            method="POST",
        )
        for _ in range(2):
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                text = self._extract_response_text(payload)
                if text:
                    data = json.loads(text)
                    if isinstance(data, dict):
                        return data
            except Exception:
                continue
        return None

    def _rule_based_extract(self, article: Dict[str, Any]) -> Dict[str, Any]:
        text = compact_whitespace(f"{article.get('title', '')} {article.get('summary', '')}")
        organizations = self._detect_organizations(text)
        raw_people = self._detect_people(text)
        people = normalize_people(raw_people, organizations=organizations, text=text)
        coins = normalize_coin_mentions(raw_people + organizations + [text], text)
        person_name = people[0] if people else ""
        buy_signal, buy_reason = self._detect_buy_signal(text)
        headline_ja = self._build_headline_ja(article, person_name, buy_reason, coins)
        return {
            "headline_ja": headline_ja,
            "topic": self._pick_topic(article, coins, organizations),
            "summary_ja": self._build_summary_ja(article, person_name, organizations, coins),
            "person_name": person_name,
            "person_role": PERSON_ROLE_MAP.get(person_name, organizations[0] if organizations else ""),
            "organization": organizations[0] if organizations else "",
            "coins": coins,
            "sentiment": self._detect_sentiment(text, article.get("market", {})),
            "market_impact": self._detect_market_impact(text, article.get("market", {})),
            "buy_signal": buy_signal,
            "buy_reason": buy_reason,
            "claim_summary": self._build_claim_summary(article),
            "image_hint": self._build_image_hint(person_name, coins, buy_signal),
            "is_crypto_related": self._is_crypto_related(text, coins, organizations),
        }

    def _merge_and_normalize(self, article: Dict[str, Any], gpt_payload: Dict[str, Any], fallback: Dict[str, Any]) -> Dict[str, Any]:
        merged = {**DEFAULT_EXTRACTION, **fallback, **{k: v for k, v in gpt_payload.items() if v not in (None, [], {})}}
        text = compact_whitespace(f"{article.get('title', '')} {article.get('summary', '')}")
        organizations = normalize_organizations([merged.get("organization", "")] + (gpt_payload.get("organizations") or []) + self._detect_organizations(text))
        people = normalize_people([merged.get("person_name", "")] + (gpt_payload.get("people") or []), organizations=organizations, text=text)
        coins = normalize_coin_mentions(merged.get("coins") or fallback.get("coins") or [], text=text)
        person_name = people[0] if people else ""
        buy_signal, buy_reason = self._detect_buy_signal(text)
        buy_signal = bool(merged.get("buy_signal")) or buy_signal
        buy_reason = compact_whitespace(merged.get("buy_reason") or buy_reason)
        headline_ja = compact_whitespace(merged.get("headline_ja") or self._build_headline_ja(article, person_name, buy_reason, coins))
        claim_summary = compact_whitespace(merged.get("claim_summary") or self._build_claim_summary(article))
        person_role = compact_whitespace(merged.get("person_role") or PERSON_ROLE_MAP.get(person_name, organizations[0] if organizations else ""))
        person = self._build_person_profile(person_name, person_role, article, buy_signal, coins)
        result = {
            **merged,
            "headline_ja": headline_ja,
            "topic": compact_whitespace(merged.get("topic") or fallback.get("topic") or "仮想通貨ニュース"),
            "summary_ja": compact_whitespace(merged.get("summary_ja") or self._build_summary_ja(article, person_name, organizations, coins)),
            "person_name": person_name,
            "person_role": person_role,
            "organization": organizations[0] if organizations else "",
            "coins": coins,
            "sentiment": self._normalize_sentiment(merged.get("sentiment")),
            "market_impact": self._normalize_market_impact(merged.get("market_impact")),
            "buy_signal": buy_signal,
            "buy_reason": buy_reason,
            "claim_summary": claim_summary,
            "image_hint": compact_whitespace(merged.get("image_hint") or self._build_image_hint(person_name, coins, buy_signal)),
            "is_crypto_related": bool(merged.get("is_crypto_related", True)),
            "people": [person_name] if person_name else [],
            "organizations": organizations,
            "headline": headline_ja or compact_whitespace(article.get("title", "")),
            "person": person,
            "article_title": article.get("title", ""),
            "article_summary": article.get("summary", ""),
            "market": article.get("market", {}),
        }
        return result

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

    def _build_person_profile(self, person_name: str, person_role: str, article: Dict[str, Any], buy_signal: bool, coins: List[str]) -> Dict[str, str]:
        if person_name and is_probable_person_name(person_name):
            summary = self._build_person_summary(article, person_name, buy_signal, coins)
            return {"name": person_name, "role": person_role or "注目投資家", "summary": summary, "avatar_mode": "person"}
        coin_hint = coins[0] if coins else "BTC"
        return {
            "name": "Market Watch",
            "role": "市場解説",
            "summary": f"人物記事が見つからないため、{coin_hint}の強気材料を基に市場イメージを表示します。",
            "avatar_mode": "fallback",
        }

    def _build_person_summary(self, article: Dict[str, Any], person_name: str, buy_signal: bool, coins: List[str]) -> str:
        coin_text = "・".join(coins[:2]) if coins else "BTC"
        if buy_signal:
            return f"{person_name}が{coin_text}への強気姿勢を示した記事です。"
        return f"{person_name}に関する発言が{coin_text}市場で注目されています。"

    def _build_headline_ja(self, article: Dict[str, Any], person_name: str, buy_reason: str, coins: List[str]) -> str:
        coin_text = "ビットコイン" if "BTC" in coins or not coins else coins[0]
        if person_name and buy_reason:
            return f"{self._to_ja_name(person_name)}「{buy_reason}」"
        if person_name:
            return f"{self._to_ja_name(person_name)}、{coin_text}に強気姿勢"
        return f"{coin_text}に強気材料、市場で注目"

    def _to_ja_name(self, name: str) -> str:
        mapping = {
            "Cathie Wood": "キャシー・ウッド",
            "Michael Saylor": "マイケル・セイラー",
            "Larry Fink": "ラリー・フィンク",
            "Brian Armstrong": "ブライアン・アームストロング",
        }
        return mapping.get(name, name)

    def _pick_topic(self, article: Dict[str, Any], coins: List[str], organizations: List[str]) -> str:
        title = (article.get("title") or "").lower()
        if coins:
            return f"{coins[0]}関連ニュース"
        if "etf" in title:
            return "ETF関連ニュース"
        if any(org in organizations for org in ("SEC", "Federal Reserve", "FOMC")):
            return "規制関連ニュース"
        return "仮想通貨ニュース"

    def _build_summary_ja(self, article: Dict[str, Any], person_name: str, organizations: List[str], coins: List[str]) -> str:
        subject = self._to_ja_name(person_name) if person_name else organizations[0] if organizations else (coins[0] if coins else "仮想通貨市場")
        base = compact_whitespace(article.get("summary") or article.get("title") or "")
        return f"{subject}に関する報道です。{base[:110]}"

    def _build_claim_summary(self, article: Dict[str, Any]) -> str:
        return compact_whitespace(article.get("summary") or article.get("title") or "")[:120]

    def _detect_buy_signal(self, text: str) -> tuple[bool, str]:
        lowered = text.lower()
        matched = [marker for marker in BUY_MARKERS if marker in lowered]
        if not matched:
            return False, ""
        if "gold" in lowered and "bitcoin" in lowered:
            return True, "ゴールドからビットコインへの資金移動を提言"
        if "accumulate" in lowered:
            return True, "ビットコインの蓄積を促す内容"
        if "price target" in lowered or "going higher" in lowered:
            return True, "ビットコインの上昇余地を強調"
        return True, "ビットコイン買いを促す強気発言"

    def _build_image_hint(self, person_name: str, coins: List[str], buy_signal: bool) -> str:
        coin = coins[0] if coins else "BTC"
        if person_name and buy_signal:
            return f"{person_name} portrait with {coin} coin, bullish market"
        if person_name:
            return f"{person_name} portrait with {coin} coin, market news"
        return f"market analyst avatar with {coin} coin, bullish market"

    def _detect_sentiment(self, text: str, market: Dict[str, Any]) -> str:
        lowered = text.lower()
        positive_markers = ["gain", "rise", "surge", "inflow", "approve", "adoption", "record", "bullish", "buy", "accumulate"]
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
        if any(keyword in lowered for keyword in ("etf", "sec", "fed", "approval", "institutional")):
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
    def _extract_response_text(payload: Dict[str, Any]) -> str:
        output = payload.get("output") or []
        for item in output:
            for content in item.get("content") or []:
                if content.get("type") in {"output_text", "text"} and content.get("text"):
                    return content["text"]
        if payload.get("output_text"):
            return payload["output_text"]
        return ""
