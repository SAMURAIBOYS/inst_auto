from __future__ import annotations

import re
from typing import Any, Dict, List

MAX_X_CAPTION_LENGTH = 180

LEADS = {
    "positive": ["市場では強気材料として注目されています。", "前向きな材料として受け止められています。"],
    "negative": ["市場では慎重な見方も出ています。", "警戒材料として受け止める向きがあります。"],
    "neutral": ["市場では注目が集まっています。", "関連テーマとして関心が高まっています。"],
}

ENDS = {
    "positive": "今後の資金フローにも注目です。",
    "negative": "今後の反応を丁寧に見たい局面です。",
    "neutral": "今後の続報が焦点になりそうです。",
}


class CaptionGenerator:
    def generate(self, article: Dict[str, Any], extraction: Dict[str, Any]) -> str:
        sentiment = extraction.get("sentiment", "neutral")
        topic = extraction.get("topic", "仮想通貨ニュース")
        people = extraction.get("people") or []
        coins = extraction.get("coins") or []
        source = article.get("source", "source")
        url = article.get("url", "")

        line1 = topic
        line2 = self._build_fact_line(article, extraction, people, coins)
        line3 = LEADS.get(sentiment, LEADS["neutral"])[0]
        line4 = ENDS.get(sentiment, ENDS["neutral"])
        source_line = self._build_source_line(source, url)
        note_line = "※要約ベース。投資判断はご自身でご確認ください。"

        caption = "\n".join([line1, line2, line3, line4, source_line, note_line])
        return self._fit_length(caption)

    def _build_fact_line(self, article: Dict[str, Any], extraction: Dict[str, Any], people: List[str], coins: List[str]) -> str:
        claim = self._compact(extraction.get("claim_summary") or extraction.get("summary_ja") or article.get("summary") or article.get("title") or "")
        subject_parts: List[str] = []
        if people:
            subject_parts.append(f"{people[0]}に関する報道")
        if coins:
            subject_parts.append("/".join(coins[:2]))
        subject = "・".join(subject_parts) if subject_parts else "記事要点"
        if claim:
            return f"{subject}: {claim}と報じられています。"
        return f"{subject}が市場で話題になっています。"

    def _build_source_line(self, source: str, url: str) -> str:
        line = f"出典: {source} {url}".strip()
        if len(line) <= 60:
            return line
        if url:
            short_url = url[:28] + "…" if len(url) > 29 else url
            line = f"出典: {source} {short_url}"
        return line

    def _fit_length(self, caption: str) -> str:
        lines = caption.splitlines()
        while len("\n".join(lines)) > MAX_X_CAPTION_LENGTH and len(lines) >= 4:
            longest = max(range(len(lines) - 2), key=lambda idx: len(lines[idx]))
            lines[longest] = self._trim_line(lines[longest])
            if len(lines[longest]) <= 8:
                break
        compact = "\n".join(lines)
        if len(compact) > MAX_X_CAPTION_LENGTH:
            lines[-2] = lines[-2].split()[0] if lines[-2].split() else "出典:"
            compact = "\n".join(lines)
        if len(compact) > MAX_X_CAPTION_LENGTH:
            lines[-1] = "※要約ベース。"
            compact = "\n".join(lines)
        return compact[:MAX_X_CAPTION_LENGTH]

    @staticmethod
    def _compact(text: str) -> str:
        text = re.sub(r"\s+", " ", str(text or "")).strip()
        text = text.replace("記事要点:", "")
        return text[:72]

    @staticmethod
    def _trim_line(text: str) -> str:
        if len(text) <= 18:
            return text
        return text[: max(10, len(text) - 14)].rstrip(" 、。,.!?:;") + "…"
