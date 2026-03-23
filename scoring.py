from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List


PERCENT_RE = re.compile(r"([+-]?\d+(?:\.\d+)?)\s*%")
VOLATILITY_WORDS = ["surge", "plunge", "jump", "crash", "record", "breakout", "selloff", "inflow", "outflow"]


@dataclass
class ScoreBreakdown:
    change_score: float
    topic_score: float
    people_score: float
    total_score: float
    should_generate: bool
    diagnostics: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "change_score": self.change_score,
            "topic_score": self.topic_score,
            "people_score": self.people_score,
            "total_score": self.total_score,
            "should_generate": self.should_generate,
            "diagnostics": self.diagnostics,
        }


class ScoringEngine:
    def __init__(self, minimum_score: float = 0.34) -> None:
        self.minimum_score = minimum_score

    def score(self, article: Dict[str, Any], extraction: Dict[str, Any], image: Dict[str, Any] | None = None) -> ScoreBreakdown:
        text = " ".join(filter(None, [article.get("title", ""), article.get("summary", "")]))
        change_score, change_diag = self._score_change(text)
        topic_score, topic_diag = self._score_topic(extraction.get("coins", []), text)
        people_score, people_diag = self._score_people(extraction.get("people", []))
        image_bonus = 0.06 if image else 0.0
        total = round(min(1.0, 0.5 * change_score + 0.3 * topic_score + 0.2 * people_score + image_bonus), 4)
        return ScoreBreakdown(
            change_score=change_score,
            topic_score=topic_score,
            people_score=people_score,
            total_score=total,
            should_generate=total >= self.minimum_score,
            diagnostics={
                "change": change_diag,
                "topic": topic_diag,
                "people": people_diag,
                "image_bonus": image_bonus,
                "minimum_score": self.minimum_score,
            },
        )

    def _score_change(self, text: str) -> tuple[float, Dict[str, Any]]:
        matches = [abs(float(match)) for match in PERCENT_RE.findall(text)]
        if matches:
            strongest = max(matches)
            score = min(1.0, strongest / 10)
            return round(score, 4), {"detected_change": strongest, "mode": "percentage"}
        keyword_hits = sum(word in text.lower() for word in VOLATILITY_WORDS)
        score = min(1.0, 0.18 + 0.16 * keyword_hits)
        return round(score, 4), {"detected_change": None, "keyword_hits": keyword_hits, "mode": "keywords"}

    def _score_topic(self, coins: List[str], text: str) -> tuple[float, Dict[str, Any]]:
        coin_count = len(coins)
        etf_bonus = 0.15 if "etf" in text.lower() else 0.0
        score = min(1.0, 0.25 + 0.25 * coin_count + etf_bonus)
        return round(score, 4), {"coin_count": coin_count, "etf_bonus": etf_bonus}

    def _score_people(self, people: List[str]) -> tuple[float, Dict[str, Any]]:
        if not people:
            return 0.0, {"has_people": False, "count": 0}
        score = min(1.0, 0.7 + 0.15 * min(2, len(people) - 1))
        return round(score, 4), {"has_people": True, "count": len(people), "lead": people[0]}
