from __future__ import annotations

import json
import re
from typing import Any, Dict, List

COIN_KEYWORDS = {
    "bitcoin": "Bitcoin",
    "btc": "Bitcoin",
    "ethereum": "Ethereum",
    "eth": "Ethereum",
    "solana": "Solana",
    "sol": "Solana",
    "xrp": "XRP",
    "ripple": "XRP",
    "dogecoin": "Dogecoin",
    "doge": "Dogecoin",
    "bnb": "BNB",
    "binance coin": "BNB",
}

ORG_KEYWORDS = [
    "BlackRock", "Coinbase", "Binance", "SEC", "Federal Reserve", "MicroStrategy",
    "Strategy", "Grayscale", "Ark Invest", "Fidelity", "Tether", "Circle",
]

NON_PERSON_TERMS = {
    "Bitcoin", "Ethereum", "Solana", "XRP", "Dogecoin", "BlackRock", "Coinbase", "Binance",
    "SEC", "ETF", "ETFs", "Federal Reserve", "MicroStrategy", "Strategy", "Grayscale", "Fidelity",
    "Tether", "Circle", "Crypto", "Cryptocurrency", "Market", "Markets", "Wall Street",
}

ORG_PERSON_MAP = {
    "BlackRock": ["Larry Fink"],
    "Coinbase": ["Brian Armstrong"],
    "Binance": ["Richard Teng", "Changpeng Zhao"],
    "MicroStrategy": ["Michael Saylor"],
    "Strategy": ["Michael Saylor"],
    "Grayscale": ["Michael Sonnenshein"],
    "Ark Invest": ["Cathie Wood"],
    "Fidelity": ["Abigail Johnson"],
    "Tether": ["Paolo Ardoino"],
    "Circle": ["Jeremy Allaire"],
}

COIN_PERSON_MAP = {
    "Bitcoin": ["Satoshi Nakamoto"],
    "Ethereum": ["Vitalik Buterin"],
    "Solana": ["Anatoly Yakovenko"],
    "XRP": ["Brad Garlinghouse"],
    "Dogecoin": ["Elon Musk"],
    "BNB": ["Changpeng Zhao"],
}

PERSON_ROLE_MAP = {
    "Cathie Wood": "ARK Invest CEO",
    "Larry Fink": "BlackRock CEO",
    "Brian Armstrong": "Coinbase CEO",
    "Richard Teng": "Binance CEO",
    "Changpeng Zhao": "Binance Founder",
    "Michael Saylor": "Strategy Executive Chairman",
    "Michael Sonnenshein": "Grayscale Executive",
    "Abigail Johnson": "Fidelity CEO",
    "Paolo Ardoino": "Tether CEO",
    "Jeremy Allaire": "Circle CEO",
    "Satoshi Nakamoto": "Bitcoin Creator",
    "Vitalik Buterin": "Ethereum Co-Founder",
    "Anatoly Yakovenko": "Solana Co-Founder",
    "Brad Garlinghouse": "Ripple CEO",
    "Elon Musk": "Dogecoin Supporter",
}


class AIExtractor:
    def extract(self, article: Dict[str, Any]) -> Dict[str, Any]:
        text = " ".join(filter(None, [article.get("title", ""), article.get("summary", "")]))
        organizations = self._detect_organizations(text)
        coins = self._detect_coins(text)
        people = self._enrich_people(self._postprocess_people(self._detect_people(text)), organizations, coins)
        topic = self._pick_topic(article, coins)
        sentiment = self._detect_sentiment(text, article.get("market", {}))
        claim_summary = self._build_claim_summary(article, people, organizations, coins)
        person = self._build_person_profile(article, people, organizations, coins)
        headline = self._build_headline(article)
        image_hint = self._build_image_hint(topic, person, organizations, coins, article.get("market", {}))
        payload = {
            "topic": topic,
            "headline": headline,
            "people": people,
            "person": person,
            "organizations": organizations,
            "coins": coins,
            "sentiment": sentiment,
            "claim_summary": claim_summary,
            "image_hint": image_hint,
            "article_title": article.get("title", ""),
            "article_summary": article.get("summary", ""),
            "market": article.get("market", {}),
        }
        return json.loads(json.dumps(payload, ensure_ascii=False))

    def _detect_people(self, text: str) -> List[str]:
        matches = re.findall(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})\b", text)
        deduped: List[str] = []
        for match in matches:
            if match not in deduped:
                deduped.append(match)
        return deduped

    def _postprocess_people(self, names: List[str]) -> List[str]:
        cleaned: List[str] = []
        for name in names:
            parts = [part for part in re.split(r"\s+", name.strip()) if part]
            if len(parts) < 2:
                continue
            if any(part in NON_PERSON_TERMS for part in parts):
                continue
            if name in NON_PERSON_TERMS:
                continue
            if name not in cleaned:
                cleaned.append(name)
        return cleaned[:3]

    def _enrich_people(self, names: List[str], organizations: List[str], coins: List[str]) -> List[str]:
        enriched = list(names)
        for organization in organizations:
            for mapped_person in ORG_PERSON_MAP.get(organization, []):
                if mapped_person not in enriched:
                    enriched.append(mapped_person)
        for coin in coins:
            for mapped_person in COIN_PERSON_MAP.get(coin, []):
                if mapped_person not in enriched:
                    enriched.append(mapped_person)
        return enriched[:3]

    def _detect_organizations(self, text: str) -> List[str]:
        found = [org for org in ORG_KEYWORDS if org.lower() in text.lower()]
        return found[:5]

    def _detect_coins(self, text: str) -> List[str]:
        found: List[str] = []
        lowered = text.lower()
        for keyword, canonical in COIN_KEYWORDS.items():
            if keyword in lowered and canonical not in found:
                found.append(canonical)
        return found[:5]

    def _detect_sentiment(self, text: str, market: Dict[str, Any]) -> str:
        lowered = text.lower()
        positive_markers = ["surge", "gain", "rise", "strong", "record", "boost", "breakout", "inflow"]
        negative_markers = ["drop", "fall", "risk", "weak", "selloff", "concern", "outflow", "crash"]
        pos = sum(marker in lowered for marker in positive_markers)
        neg = sum(marker in lowered for marker in negative_markers)
        change = float(market.get("btc_change_percent", 0.0) or 0.0)
        if change > 0.3:
            pos += 1
        elif change < -0.3:
            neg += 1
        if pos > neg:
            return "positive"
        if neg > pos:
            return "negative"
        return "neutral"

    def _pick_topic(self, article: Dict[str, Any], coins: List[str]) -> str:
        title = article.get("title", "")
        if coins:
            return f"{coins[0]}関連ニュース"
        if "ETF" in title.upper():
            return "ETF関連ニュース"
        return "仮想通貨マーケットニュース"

    def _build_claim_summary(self, article: Dict[str, Any], people: List[str], organizations: List[str], coins: List[str]) -> str:
        title = article.get("title", "")
        summary = article.get("summary", "")
        subject_parts = []
        if coins:
            subject_parts.append("・".join(coins[:2]))
        if organizations:
            subject_parts.append("・".join(organizations[:2]))
        if people:
            subject_parts.append(people[0])
        subject = " / ".join(subject_parts) if subject_parts else "仮想通貨市場"
        base = re.sub(r"\s+", " ", (summary or title or "最新の仮想通貨ニュース")).strip()
        return f"{subject}が注目テーマ。記事要点: {base[:130]}"

    def _build_person_profile(self, article: Dict[str, Any], people: List[str], organizations: List[str], coins: List[str]) -> Dict[str, str]:
        if people:
            name = people[0]
            role = PERSON_ROLE_MAP.get(name) or self._infer_role(name, organizations, coins)
            summary = self._build_person_summary(article, name, role)
            avatar_mode = "person"
        else:
            name = "Market Watch"
            role = "Fallback Avatar"
            summary = "主要人物が不明なため、その日の市場ムードを示す代替アバター表示。"
            avatar_mode = "fallback"
        return {
            "name": name,
            "role": role,
            "summary": summary,
            "avatar_mode": avatar_mode,
        }

    def _infer_role(self, name: str, organizations: List[str], coins: List[str]) -> str:
        if organizations:
            return f"{organizations[0]} key figure"
        if coins:
            return f"{coins[0]} market commentator"
        return f"Crypto market figure"

    def _build_person_summary(self, article: Dict[str, Any], name: str, role: str) -> str:
        summary = re.sub(r"\s+", " ", article.get("summary", "")).strip() or article.get("title", "")
        lead = summary[:72]
        return f"{role}として{lead}"

    def _build_headline(self, article: Dict[str, Any]) -> str:
        title = re.sub(r"\s+", " ", article.get("title", "")).strip()
        return title[:96]

    def _build_image_hint(self, topic: str, person: Dict[str, str], organizations: List[str], coins: List[str], market: Dict[str, Any]) -> str:
        mood = market.get("btc_direction", "neutral")
        lead_word = self._pick_buzz_word(coins, mood)
        name = person.get("name", "fallback avatar")
        role = person.get("role", "market watcher")
        if person.get("avatar_mode") == "person":
            return f"人物左配置、BTC右配置。{name} ({role}) を軸に『{lead_word}』を表示。"
        org_hint = ", ".join(organizations[:2]) or "市場キーワード"
        coin_hint = ", ".join(coins[:2]) or "主要コイン"
        return f"fallback avatar と {org_hint}/{coin_hint} を使い、『{lead_word}』を表示。"

    @staticmethod
    def _pick_buzz_word(coins: List[str], mood: str) -> str:
        if mood == "up":
            return "GREEN MOVE"
        if mood == "down":
            return "RISK OFF"
        if "Bitcoin" in coins:
            return "BTC WATCH"
        return "ALERT"
