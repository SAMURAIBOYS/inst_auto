from __future__ import annotations

import re
from typing import Any, Dict

MAX_X_CAPTION_LENGTH = 180


class CaptionGenerator:
    def generate(self, article: Dict[str, Any], extraction: Dict[str, Any]) -> str:
        source = article.get("source", "source")
        url = article.get("url", "")
        headline = extraction.get("headline_ja") or extraction.get("topic") or "仮想通貨ニュース"
        person = extraction.get("person_name") or (extraction.get("people") or [""])[0]
        coins = extraction.get("coins") or []
        claim = self._compact(extraction.get("claim_summary") or extraction.get("summary_ja") or article.get("summary") or article.get("title") or "")
        buy_reason = self._compact(extraction.get("buy_reason") or "")
        coin_text = "・".join(coins[:2]) if coins else "BTC"

        lines = [headline]
        if person and buy_reason:
            lines.append(f"{person}については、{buy_reason}と報じられています。")
        elif person:
            lines.append(f"{person}に関する発言として、{claim}と報じられています。")
        else:
            lines.append(f"{coin_text}市場では、{claim}とみられています。")
        lines.append("断定ではなく、今後の値動きや続報に注目です。")
        lines.append(self._build_source_line(source, url))
        lines.append("※要約ベース。投資判断はご自身でご確認ください。")
        return self._fit_length("\n".join(lines))

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
            new_line = self._trim_line(lines[longest])
            if new_line == lines[longest]:
                break
            lines[longest] = new_line
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
        return text[:72]

    @staticmethod
    def _trim_line(text: str) -> str:
        if len(text) <= 18:
            return text
        trimmed = text[: max(10, len(text) - 14)].rstrip(" 、。,.!?:;") + "…"
        return trimmed
