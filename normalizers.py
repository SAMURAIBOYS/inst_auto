from __future__ import annotations

import re
from typing import Iterable, List, Sequence

COIN_ALIASES = {
    "bitcoin": "BTC",
    "btc": "BTC",
    "xbt": "BTC",
    "ethereum": "ETH",
    "eth": "ETH",
    "ether": "ETH",
    "ripple": "XRP",
    "xrp": "XRP",
    "solana": "SOL",
    "sol": "SOL",
    "dogecoin": "DOGE",
    "doge": "DOGE",
    "cardano": "ADA",
    "ada": "ADA",
    "binance coin": "BNB",
    "bnb": "BNB",
    "litecoin": "LTC",
    "ltc": "LTC",
    "tron": "TRX",
    "trx": "TRX",
}

NON_PERSON_TERMS = {
    "bitcoin", "btc", "xbt", "ethereum", "eth", "ether", "xrp", "sol", "solana", "doge", "dogecoin", "ada", "cardano",
    "blackrock", "grayscale", "coinbase", "binance", "metaplanet", "microstrategy", "strategy", "tesla", "fidelity", "ark", "ark invest",
    "sec", "fed", "fomc", "etf", "spot etf", "bitcoin etf", "ethereum etf", "ripple", "circle", "tether", "crypto", "cryptocurrency",
    "market", "markets", "wall street", "us", "u.s.", "japan", "china", "europe", "nasdaq", "nyse", "gold",
}

ORG_HINTS = (
    "inc", "corp", "corporation", "llc", "ltd", "plc", "group", "capital", "invest", "investments", "asset", "management",
    "holdings", "fund", "etf", "trust", "exchange", "commission", "agency", "department", "bank", "reserve", "foundation",
    "labs", "protocol", "dao", "ventures", "partners", "university", "government", "ministry", "magazine", "news", "media",
)

STOPWORDS = {"the", "a", "an", "and", "of", "for", "to", "in", "on", "at"}


def compact_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip()


def normalize_coin_mentions(values: Sequence[str] | None, text: str = "") -> List[str]:
    candidates = [compact_whitespace(v).lower() for v in (values or []) if compact_whitespace(v)]
    haystack = f" {' '.join(candidates)} {compact_whitespace(text).lower()} "
    coins: List[str] = []
    for alias, ticker in COIN_ALIASES.items():
        if re.search(rf"(?<![A-Za-z0-9]){re.escape(alias)}(?![A-Za-z0-9])", haystack):
            if ticker not in coins:
                coins.append(ticker)
    return coins


def looks_like_ticker(text: str) -> bool:
    raw = compact_whitespace(text)
    return bool(re.fullmatch(r"[A-Z]{2,6}", raw))


def looks_like_organization(text: str) -> bool:
    lowered = compact_whitespace(text).lower()
    if not lowered:
        return False
    if lowered in NON_PERSON_TERMS:
        return True
    return any(hint in lowered for hint in ORG_HINTS)


def is_probable_person_name(text: str) -> bool:
    name = compact_whitespace(text)
    if len(name) <= 2:
        return False
    if looks_like_ticker(name) or looks_like_organization(name):
        return False
    lowered = name.lower()
    if lowered in NON_PERSON_TERMS:
        return False
    parts = [p for p in re.split(r"\s+", name) if p]
    if not (1 <= len(parts) <= 4):
        return False
    if len(parts) == 1 and parts[0].lower() in STOPWORDS:
        return False
    if not any(ch.isalpha() for ch in name):
        return False
    if len(parts) == 1:
        return parts[0][:1].isupper() and parts[0][1:].islower()
    return all(part[:1].isupper() for part in parts if part)


def normalize_people(values: Iterable[str] | None, organizations: Sequence[str] | None = None, text: str = "") -> List[str]:
    organizations_lower = {compact_whitespace(v).lower() for v in (organizations or []) if compact_whitespace(v)}
    normalized: List[str] = []
    for raw in values or []:
        name = compact_whitespace(raw).strip("-–—:;,. ")
        if len(name) <= 1:
            continue
        if looks_like_ticker(name):
            continue
        lowered = name.lower()
        if lowered in NON_PERSON_TERMS or lowered in organizations_lower:
            continue
        if looks_like_organization(name):
            continue
        if not is_probable_person_name(name):
            continue
        parts = [p for p in re.split(r"\s+", name) if p]
        canonical = " ".join(part[:1].upper() + part[1:] if part.islower() else part for part in parts)
        if canonical.lower() in NON_PERSON_TERMS:
            continue
        if canonical not in normalized:
            normalized.append(canonical)
    return normalized


def normalize_organizations(values: Iterable[str] | None) -> List[str]:
    organizations: List[str] = []
    for raw in values or []:
        name = compact_whitespace(raw).strip("-–—:;,. ")
        if len(name) <= 1:
            continue
        if name not in organizations:
            organizations.append(name)
    return organizations
