from __future__ import annotations

import re
from typing import Any, Dict, List

MAX_X_CAPTION_LENGTH = 180
MIN_X_CAPTION_LENGTH = 100

HOOKS = {
    "positive": "これヤバい🔥",
    "negative": "警戒すべき分岐点⚠️",
    "neutral": "次の分岐点かも⚠️",
}

CTA = {
    "positive": "資金の向きが変わる前に要チェック。",
    "negative": "ここでの判断ミスは痛いかもしれません。",
    "neutral": "次の一手を考える材料になりそうです。",
}


class CaptionGenerator:
    def generate(self, article: Dict[str, Any], extraction: Dict[str, Any]) -> str:
        sentiment = extraction.get("sentiment", "neutral")
        hook = HOOKS.get(sentiment, HOOKS["neutral"])
        topic = extraction.get("topic", "仮想通貨ニュース")
        claim_summary = self._compact(extraction.get("claim_summary", ""))
        person = extraction.get("person") or {}
        market = extraction.get("market") or {}
        source_name = article.get("source", "source")
        url = article.get("url", "")

        market_line = self._market_line(market)
        person_line = self._person_line(person)
        body_lines: List[str] = [
            hook,
            topic,
            claim_summary,
            person_line,
            market_line,
            CTA.get(sentiment, CTA["neutral"]),
        ]
        body = "\n".join(line for line in body_lines if line)
        source_line = f"出典: {source_name} {url}".strip()
        note_line = "※要約ベース。投資判断は自己責任。"
        caption = "\n".join([body, source_line, note_line])
        return self._fit_x_length(caption)

    def _fit_x_length(self, caption: str) -> str:
        lines = caption.splitlines()
        body_lines = lines[:-2]
        source_line, note_line = lines[-2:]

        for _ in range(16):
            current_caption = "\n".join([*body_lines, source_line, note_line])
            if len(current_caption) <= MAX_X_CAPTION_LENGTH:
                caption = current_caption
                break

            next_caption = current_caption
            longest_index = max(range(len(body_lines)), key=lambda idx: len(body_lines[idx]), default=None)
            if longest_index is not None:
                trimmed = self._trim_line(body_lines[longest_index])
                if trimmed != body_lines[longest_index]:
                    body_lines[longest_index] = trimmed
                    next_caption = "\n".join([*body_lines, source_line, note_line])
            if next_caption != current_caption:
                caption = next_caption
                continue

            shortened_source_line = self._shorten_source_line(source_line)
            if shortened_source_line != source_line:
                source_line = shortened_source_line
                caption = "\n".join([*body_lines, source_line, note_line])
                continue

            dropped_url_line = self._drop_url(source_line)
            if dropped_url_line != source_line:
                source_line = dropped_url_line
                caption = "\n".join([*body_lines, source_line, note_line])
                continue

            caption = self._safe_fallback_caption(body_lines, source_line, note_line)
            break
        else:
            caption = self._safe_fallback_caption(body_lines, source_line, note_line)

        if len(caption) < MIN_X_CAPTION_LENGTH:
            body_lines.append("市場の温度感が一気に変わる可能性も。")
            caption = "\n".join([*body_lines, source_line, note_line])
            if len(caption) > MAX_X_CAPTION_LENGTH:
                body_lines[-1] = self._trim_line(body_lines[-1])
                caption = "\n".join([*body_lines, source_line, note_line])
        return caption

    @staticmethod
    def _compact(text: str) -> str:
        compact = re.sub(r"\s+", " ", text).strip()
        compact = compact.replace("記事要点:", "")
        return compact[:64]

    @staticmethod
    def _person_line(person: Dict[str, Any]) -> str:
        name = person.get("name") or "人物不明"
        role = person.get("role") or "市場関係者"
        return f"{name} / {role}"

    @staticmethod
    def _market_line(market: Dict[str, Any]) -> str:
        price = market.get("btc_price")
        change = market.get("btc_change_percent")
        direction = market.get("btc_direction", "neutral")
        if price is None or change is None:
            return ""
        mood = {"bullish": "上向き", "bearish": "下向き", "neutral": "様子見"}.get(direction, "様子見")
        return f"BTC ${price:,.2f} / {change:+.2f}% / {mood}"

    @staticmethod
    def _trim_line(text: str) -> str:
        if len(text) <= 18:
            return text
        trimmed = text[: max(10, len(text) - 12)].rstrip(" 、。,.!")
        return trimmed + "…"

    @staticmethod
    def _shorten_source_line(source_line: str) -> str:
        parts = source_line.split()
        if len(parts) < 3:
            return source_line
        prefix = " ".join(parts[:-1])
        url = parts[-1]
        if len(url) <= 24:
            return source_line
        return f"{prefix} {url[:21]}…"

    @staticmethod
    def _drop_url(source_line: str) -> str:
        parts = source_line.split()
        if len(parts) < 3:
            return source_line
        return " ".join(parts[:-1])

    @staticmethod
    def _safe_fallback_caption(body_lines: List[str], source_line: str, note_line: str) -> str:
        compact_body = body_lines[:4]
        compact_body[-1] = CaptionGenerator._trim_line(compact_body[-1])
        return "\n".join([*compact_body, source_line, note_line])
