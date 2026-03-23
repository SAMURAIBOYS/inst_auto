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

PERSON_ROLE_MAP = {
    "Cathie Wood": ("ARK Invest CEO", "Investor backing a strong long-term Bitcoin case."),
    "Larry Fink": ("BlackRock CEO", "Asset-management executive steering institutional crypto adoption."),
    "Brian Armstrong": ("Coinbase CEO", "Exchange founder commenting on crypto market structure."),
    "Richard Teng": ("Binance CEO", "Exchange leader tied to major trading and regulation themes."),
    "Changpeng Zhao": ("Binance founder", "High-profile crypto executive often tied to market sentiment."),
    "Michael Saylor": ("Strategy chairman", "Corporate Bitcoin advocate pushing treasury accumulation."),
    "Michael Sonnenshein": ("Grayscale executive", "Institutional crypto product operator tied to ETF narratives."),
    "Abigail Johnson": ("Fidelity CEO", "Traditional-finance executive linked to digital asset expansion."),
    "Paolo Ardoino": ("Tether CEO", "Stablecoin operator speaking on liquidity and reserves."),
    "Jeremy Allaire": ("Circle CEO", "Stablecoin executive focused on digital-dollar adoption."),
    "Satoshi Nakamoto": ("Bitcoin creator", "Fallback avatar used when no clear human source is extracted."),
    "Vitalik Buterin": ("Ethereum co-founder", "Builder associated with Ethereum roadmap and adoption."),
    "Anatoly Yakovenko": ("Solana co-founder", "Protocol builder associated with Solana network growth."),
    "Brad Garlinghouse": ("Ripple CEO", "Executive associated with XRP and Ripple market narratives."),
    "Elon Musk": ("Entrepreneur", "Market-moving public figure frequently tied to meme-coin sentiment."),
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


class AIExtractor:
    def extract(self, article: Dict[str, Any]) -> Dict[str, Any]:
        text = " ".join(filter(None, [article.get("title", ""), article.get("summary", "")]))
        organizations = self._detect_organizations(text)
        coins = self._detect_coins(text)
        people = self._enrich_people(self._postprocess_people(self._detect_people(text)), organizations, coins)
        sentiment = self._detect_sentiment(text)
        claim_summary = self._build_claim_summary(article, people, organizations, coins)
        topic = self._pick_topic(article, coins)
        person = self._build_person(article, people, organizations, coins)
        image_hint = self._build_image_hint(topic, person, organizations, coins, sentiment)
        payload = {
            "topic": topic,
            "people": people,
            "person": person,
            "organizations": organizations,
            "coins": coins,
            "sentiment": sentiment,
            "claim_summary": claim_summary,
            "headline_display": self._headline_display(article.get("title", topic)),
            "image_hint": image_hint,
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
        if not enriched:
            enriched.append("Satoshi Nakamoto")
        return enriched[:3]

    def _build_person(self, article: Dict[str, Any], people: List[str], organizations: List[str], coins: List[str]) -> Dict[str, Any]:
        primary = people[0] if people else "Satoshi Nakamoto"
        role, default_summary = PERSON_ROLE_MAP.get(primary, ("Market participant", "Public figure connected to the current crypto headline."))
        if organizations and primary == "Satoshi Nakamoto":
            org = organizations[0]
            role = f"{org} figure"
            default_summary = f"Fallback profile used because the article did not expose a clear individual spokesperson from {org}."
        elif coins and primary == "Satoshi Nakamoto":
            role = f"{coins[0]} proxy figure"
            default_summary = f"Fallback profile used because the article centers on {coins[0]} without a clear named individual."
        summary_source = re.sub(r"\s+", " ", article.get("summary") or article.get("title") or default_summary).strip()
        short_summary = summary_source[:96].rstrip(" .,;")
        if short_summary and short_summary != default_summary[:96].rstrip(" .,;"):
            summary = short_summary
        else:
            summary = default_summary
        return {
            "name": primary,
            "role": role,
            "summary": summary,
            "fallback_avatar": primary == "Satoshi Nakamoto",
        }

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

    def _detect_sentiment(self, text: str) -> str:
        lowered = text.lower()
        positive_markers = ["surge", "gain", "rise", "strong", "record", "boost", "breakout", "inflow", "bull"]
        negative_markers = ["drop", "fall", "risk", "weak", "selloff", "concern", "outflow", "crash", "bear"]
        pos = sum(marker in lowered for marker in positive_markers)
        neg = sum(marker in lowered for marker in negative_markers)
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

    def _headline_display(self, headline: str) -> str:
        compact = re.sub(r"[^A-Za-z0-9$%,'()/:\-\s]", " ", headline.upper())
        compact = re.sub(r"\s+", " ", compact).strip()
        return compact[:88]

    def _build_image_hint(self, topic: str, person: Dict[str, Any], organizations: List[str], coins: List[str], sentiment: str) -> str:
        lead_word = self._pick_buzz_word(coins, sentiment)
        person_name = person.get("name") or "fallback avatar"
        role = person.get("role") or "market participant"
        org_hint = ", ".join(organizations[:2]) or "market"
        coin_hint = ", ".join(coins[:2]) or "BTC"
        return (
            f"Retro pixel card with {person_name} on the left, {role} sublabel, {coin_hint} on the right, "
            f"headline bar on top, and {lead_word} mood cues reflecting {org_hint}."
        )

    @staticmethod
    def _pick_buzz_word(coins: List[str], sentiment: str) -> str:
        if sentiment == "positive":
            return "PUMP"
        if sentiment == "negative":
            return "RISK"
        if "Bitcoin" in coins:
            return "BTC WATCH"
        return "ALERT"
