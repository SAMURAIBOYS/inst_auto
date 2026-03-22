from __future__ import annotations

import json
import random
import time
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from improver import ImprovementEngine
from scoring import ScoringEngine


@dataclass
class GenerationResult:
    caption: str
    summary: str
    people: List[str]
    image: Dict[str, Any]
    prompt_used: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "caption": self.caption,
            "summary": self.summary,
            "people": self.people,
            "image": self.image,
            "prompt_used": self.prompt_used,
        }


class APIError(RuntimeError):
    pass


class AutoImprovementLoop:
    def __init__(
        self,
        output_dir: str | Path = ".",
        max_attempts: int = 5,
        retry_limit: int = 3,
        seed: int = 7,
    ) -> None:
        self.output_dir = Path(output_dir)
        self.logs_dir = self.output_dir / "logs"
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.best_result_path = self.output_dir / "best_result.json"
        self.max_attempts = max_attempts
        self.retry_limit = retry_limit
        self.random = random.Random(seed)
        self.scorer = ScoringEngine()
        self.improver = ImprovementEngine()

    def run(self, source: Dict[str, Any], initial_config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        config = deepcopy(initial_config or self.default_config())
        history: List[Dict[str, Any]] = []
        best_record = self._load_best_result()

        for attempt in range(1, self.max_attempts + 1):
            generation = self._with_retry(lambda: self.generate_candidate(source, config, attempt))
            score = self.scorer.score(source, generation.to_dict()).to_dict()
            record = {
                "attempt": attempt,
                "timestamp": self._timestamp(),
                "config": deepcopy(config),
                "generation": generation.to_dict(),
                "score": score,
            }
            history.append(record)
            self._write_attempt_log(record)

            if self._is_better(score, best_record.get("score") if best_record else None):
                best_record = record
                self._write_json(self.best_result_path, best_record)

            if score["total_score"] >= config["thresholds"]["target_score"]:
                best_record["status"] = "target_reached"
                self._write_json(self.best_result_path, best_record)
                break

            config, changes = self.improver.improve(config, score, history)
            record["improvements_applied"] = changes
            self._write_attempt_log(record)
        else:
            if best_record:
                best_record["status"] = "max_attempts_reached"
                self._write_json(self.best_result_path, best_record)

        return {
            "best_result": best_record,
            "history": history,
            "attempt_count": len(history),
            "best_result_path": str(self.best_result_path),
            "logs_dir": str(self.logs_dir),
        }

    def generate_candidate(self, source: Dict[str, Any], config: Dict[str, Any], attempt: int) -> GenerationResult:
        self._simulate_possible_api_failure(attempt)
        people = self._extract_people(source, config)
        title = source.get("title", "Untitled")
        summary = self._build_summary(source, people, config)
        caption = f"{title} — {summary}"
        image = self._render_layout(source, caption, config)
        return GenerationResult(
            caption=caption,
            summary=summary,
            people=people,
            image=image,
            prompt_used=config["prompt_template"],
        )

    def _extract_people(self, source: Dict[str, Any], config: Dict[str, Any]) -> List[str]:
        provided_people = list(source.get("people", []))
        if provided_people:
            return provided_people

        text = " ".join(filter(None, [source.get("title", ""), source.get("summary", "")]))
        capitalized = []
        tokens = text.replace("\n", " ").split()
        current: List[str] = []
        for token in tokens:
            cleaned = token.strip(",.!?()[]{}\"'")
            if cleaned[:1].isupper() and cleaned.lower() not in {"the", "a", "an", "in", "on", "and"}:
                current.append(cleaned)
            elif current:
                if len(current) >= 2:
                    capitalized.append(" ".join(current))
                current = []
        if current and len(current) >= 2:
            capitalized.append(" ".join(current))

        if capitalized:
            return capitalized[:3]
        if config["extraction"]["use_fallback"]:
            return [source.get("fallback_person", "Unknown Person")]
        return []

    def _build_summary(self, source: Dict[str, Any], people: List[str], config: Dict[str, Any]) -> str:
        base = source.get("summary") or source.get("title", "")
        keywords = source.get("keywords", [])
        keyword_text = ", ".join(keywords[:3]) if keywords else "key context"
        people_text = ", ".join(people) if people else "the subject"
        tone = config.get("tone", "concise")
        improvement_count = config.get("meta", {}).get("improvement_count", 0)
        if improvement_count >= 2:
            base_excerpt = base[:108].rstrip(" ,.")
            return (
                f"{people_text} lead a {tone} update on {keyword_text}. "
                f"Source-aligned takeaway: {base_excerpt}."
            )
        return (
            f"{people_text} are featured in a {tone} recap focused on {keyword_text}. "
            f"It stays aligned with the source: {base[:160].rstrip()}"
        )

    def _render_layout(self, source: Dict[str, Any], caption: str, config: Dict[str, Any]) -> Dict[str, Any]:
        layout = config["layout"]
        width = layout["canvas_width"]
        height = layout["canvas_height"]
        font_size = layout["font_size"]
        contrast = layout["contrast"]
        safe_margin = layout["safe_margin"]
        headline_chars = len(source.get("title", ""))
        text_density = min(0.95, max(0.05, len(caption) / (width * height / 1800)))
        overflow = (headline_chars > 110) or (text_density > 0.78)
        return {
            "width": width,
            "height": height,
            "font_size": font_size,
            "contrast": round(contrast, 2),
            "text_density": round((text_density + layout["text_density_target"]) / 2, 4),
            "headline_chars": headline_chars,
            "safe_margin": safe_margin,
            "overflow": overflow,
        }

    def _with_retry(self, operation):
        last_error: Exception | None = None
        for attempt in range(1, self.retry_limit + 1):
            try:
                return operation()
            except APIError as exc:
                last_error = exc
                time.sleep(0.05 * attempt)
        raise RuntimeError(f"generation failed after {self.retry_limit} retries") from last_error

    def _simulate_possible_api_failure(self, attempt: int) -> None:
        if attempt == 1 and self.random.random() < 0.15:
            raise APIError("simulated transient API failure")

    def _load_best_result(self) -> Optional[Dict[str, Any]]:
        if not self.best_result_path.exists():
            return None
        with self.best_result_path.open("r", encoding="utf-8") as fp:
            return json.load(fp)

    def _is_better(self, score: Dict[str, Any], current_best_score: Optional[Dict[str, Any]]) -> bool:
        if current_best_score is None:
            return True
        return score["total_score"] > current_best_score["total_score"]

    def _write_attempt_log(self, payload: Dict[str, Any]) -> None:
        filename = f"attempt_{payload['attempt']:02d}.json"
        self._write_json(self.logs_dir / filename, payload)

    @staticmethod
    def _write_json(path: Path, payload: Dict[str, Any]) -> None:
        with path.open("w", encoding="utf-8") as fp:
            json.dump(payload, fp, ensure_ascii=False, indent=2)

    @staticmethod
    def _timestamp() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def default_config() -> Dict[str, Any]:
        return {
            "prompt_template": (
                "Create a social post with an image concept and concise summary."
                " Prioritize factual consistency, readability, and named person accuracy."
            ),
            "tone": "concise",
            "layout": {
                "canvas_width": 1080,
                "canvas_height": 1080,
                "font_size": 22,
                "contrast": 0.74,
                "text_density_target": 0.35,
                "safe_margin": 0.06,
            },
            "extraction": {
                "use_fallback": False,
                "capitalized_name_bias": 0.55,
            },
            "thresholds": {
                "retry_score": 0.72,
                "target_score": 0.88,
                "person_accuracy": 0.8,
                "image_readability": 0.72,
                "source_alignment": 0.68,
            },
            "meta": {
                "improvement_count": 0,
                "last_changes": [],
            },
        }
