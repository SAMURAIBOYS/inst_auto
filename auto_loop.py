from __future__ import annotations

import json
import shutil
import traceback
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from ai_extract import AIExtractor
from generate_caption import CaptionGenerator
from generate_image import ImageGenerator
from improver import ImprovementEngine
from news_fetcher import NewsFetcher
from scoring import ScoringEngine


@dataclass
class PipelineArtifacts:
    article: Dict[str, Any]
    extraction: Dict[str, Any]
    caption: str
    image: Dict[str, Any]
    fetch_mode: str
    fetch_errors: List[str]
    score: Dict[str, Any]
    improvements: List[str]
    skipped_regeneration: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "article": self.article,
            "extraction": self.extraction,
            "caption": self.caption,
            "image": self.image,
            "fetch_mode": self.fetch_mode,
            "fetch_errors": self.fetch_errors,
            "score": self.score,
            "improvements": self.improvements,
            "skipped_regeneration": self.skipped_regeneration,
        }


class AutoImprovementLoop:
    def __init__(self, output_dir: str | Path = "output", max_attempts: int = 2) -> None:
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir = self.output_dir / "logs"
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.best_result_path = self.output_dir / "best_result.json"
        self.latest_text_path = self.output_dir / "latest.txt"
        self.fetcher = NewsFetcher(sample_path=self.output_dir / "sample_news.json")
        self.extractor = AIExtractor()
        self.caption_generator = CaptionGenerator()
        self.image_generator = ImageGenerator(output_dir=self.output_dir)
        self.scorer = ScoringEngine()
        self.improver = ImprovementEngine(best_result_path=self.best_result_path)
        self.max_attempts = max_attempts

    def run(self) -> Dict[str, Any]:
        run_errors: List[str] = []
        fetched = self.fetcher.fetch_latest()
        article = fetched.article
        best_artifacts: PipelineArtifacts | None = None
        best_score = -1.0
        history: List[Dict[str, Any]] = []
        extraction = self.extractor.extract(article)

        for attempt in range(1, self.max_attempts + 1):
            improvements: List[str] = []
            skipped_regeneration = False
            try:
                pre_score = self.scorer.score(article, extraction).to_dict()
                if not pre_score.get("should_generate", True):
                    skipped_regeneration = True
                    improvements.append("score below threshold -> skipped retry loop for this attempt")
                if attempt > 1 or skipped_regeneration:
                    extraction, improve_changes = self.improver.improve(extraction, pre_score)
                    improvements.extend(improve_changes)

                caption = self.caption_generator.generate(article, extraction)
                image = self.image_generator.generate(extraction, caption=caption)
                final_score = self.scorer.score(article, extraction, image=image).to_dict()
                artifacts = PipelineArtifacts(
                    article=article,
                    extraction=extraction,
                    caption=caption,
                    image=image,
                    fetch_mode=fetched.mode,
                    fetch_errors=fetched.errors + run_errors,
                    score=final_score,
                    improvements=improvements,
                    skipped_regeneration=skipped_regeneration,
                )
            except Exception as exc:  # noqa: BLE001
                run_errors.append(f"attempt_{attempt}_failed: {exc}")
                run_errors.append(traceback.format_exc(limit=2))
                caption = self._fallback_caption(article)
                image = self.image_generator.generate({
                    "topic": "CRYPTO ALERT",
                    "people": ["Satoshi Nakamoto"],
                    "organizations": [],
                    "coins": ["Bitcoin"],
                    "sentiment": "neutral",
                    "claim_summary": article.get("title", "Fallback summary"),
                    "image_hint": "fallback image",
                }, caption=caption)
                artifacts = PipelineArtifacts(
                    article=article,
                    extraction=extraction,
                    caption=caption,
                    image=image,
                    fetch_mode=fetched.mode,
                    fetch_errors=fetched.errors + run_errors,
                    score={"total_score": 0.0, "should_generate": True, "diagnostics": {}},
                    improvements=["exception fallback executed"],
                    skipped_regeneration=False,
                )

            record = {
                "attempt": attempt,
                "generated_at": self._timestamp(),
                "result": artifacts.to_dict(),
            }
            history.append(record)
            self._write_json(self.logs_dir / f"attempt_{attempt:02d}.json", record)

            attempt_score = float(artifacts.score.get("total_score", 0.0))
            if attempt_score > best_score:
                best_score = attempt_score
                best_artifacts = artifacts

            if artifacts.score.get("should_generate", True) and attempt_score >= 0.6:
                break

            extraction, improve_changes = self.improver.improve(extraction, artifacts.score)
            if best_artifacts:
                best_artifacts.improvements.extend(change for change in improve_changes if change not in best_artifacts.improvements)

        assert best_artifacts is not None
        self._restore_latest_image(best_artifacts)
        self.latest_text_path.write_text(best_artifacts.caption, encoding="utf-8")
        payload = {
            "generated_at": self._timestamp(),
            "result": best_artifacts.to_dict(),
            "history_length": len(history),
        }
        self._write_json(self.best_result_path, payload)
        return {
            "best_result_path": str(self.best_result_path),
            "latest_text_path": str(self.latest_text_path),
            "latest_image_path": best_artifacts.image.get("latest_path"),
            "fetch_mode": fetched.mode,
            "fetch_errors": fetched.errors + run_errors,
            "result": best_artifacts.to_dict(),
            "history_length": len(history),
        }

    @staticmethod
    def _fallback_caption(article: Dict[str, Any]) -> str:
        source = article.get("source", "source")
        url = article.get("url", "")
        return f"これヤバい⚠️\n速報を整理中\n{article.get('title', 'Crypto alert')}\n出典: {source} {url}\n※要約ベース。投資判断は自己責任。"

    @staticmethod
    def _write_json(path: Path, payload: Dict[str, Any]) -> None:
        with path.open("w", encoding="utf-8") as fp:
            json.dump(payload, fp, ensure_ascii=False, indent=2)

    @staticmethod
    def _timestamp() -> str:
        return datetime.now(timezone.utc).isoformat()

    def _restore_latest_image(self, artifacts: PipelineArtifacts) -> None:
        winning_image = Path(artifacts.image.get("path", ""))
        latest_image = Path(artifacts.image.get("latest_path", self.output_dir / "latest.png"))
        if not winning_image.exists():
            return
        latest_image.parent.mkdir(parents=True, exist_ok=True)
        if winning_image.resolve() != latest_image.resolve():
            shutil.copyfile(winning_image, latest_image)
        artifacts.image["latest_path"] = str(latest_image)
