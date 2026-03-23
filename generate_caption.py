from __future__ import annotations

import re
from typing import Any, Dict, List


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
        source_name = article.get("source", "source")
        url = article.get("url", "")

        body_lines: List[str] = [
            hook,
            f"{topic}",
            claim_summary,
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
        ending = lines[-2:]
        body = "\n".join(body_lines)

        while len(caption) > 180 and body_lines:
            longest_index = max(range(len(body_lines)), key=lambda idx: len(body_lines[idx]))
            body_lines[longest_index] = self._trim_line(body_lines[longest_index])
            body = "\n".join(body_lines)
            caption = "\n".join([body, *ending])

        if len(caption) < 100:
            body_lines.append("市場の温度感が一気に変わる可能性も。")
            body = "\n".join(body_lines)
            caption = "\n".join([body, *ending])
            if len(caption) > 180:
                caption = self._fit_x_length(caption)
        return caption

    @staticmethod
    def _compact(text: str) -> str:
        compact = re.sub(r"\s+", " ", text).strip()
        compact = compact.replace("記事要点:", "")
        return compact[:64]

    @staticmethod
    def _trim_line(text: str) -> str:
        if len(text) <= 18:
            return text
        trimmed = text[: max(10, len(text) - 12)].rstrip(" 、。,.!")
        return trimmed + "…"
