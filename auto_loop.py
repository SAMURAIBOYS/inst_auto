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
    person: Dict[str, Any]
    market: Dict[str, Any]
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
            "person": self.person,
            "market": self.market,
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
        self.archive_root = self.output_dir.parent / "archive" if self.output_dir.name == "output" else self.output_dir / "archive"
        self.archive_root.mkdir(parents=True, exist_ok=True)
        self.fetcher = NewsFetcher(sample_path=self.output_dir / "sample_news.json")
        self.extractor = AIExtractor()
        self.caption_generator = CaptionGenerator()
        self.image_generator = ImageGenerator(output_dir=self.output_dir, archive_root=self.archive_root)
        self.scorer = ScoringEngine()
        self.improver = ImprovementEngine(best_result_path=self.best_result_path)
        self.max_attempts = max_attempts

    def run(self) -> Dict[str, Any]:
        run_errors: List[str] = []
        fetched = self.fetcher.fetch_latest()
        market_fetch = getattr(self.fetcher, "fetch_market", None)
        market = market_fetch() if callable(market_fetch) else {"btc_price": 65000.0, "btc_change_percent": 0.0, "btc_direction": "neutral", "source": "fallback:test_stub", "errors": []}
        article = fetched.article
        best_artifacts: PipelineArtifacts | None = None
        best_score = -1.0
        history: List[Dict[str, Any]] = []
        extraction = self.extractor.extract(article)
        extraction["market"] = market

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
                    extraction["market"] = market

                caption = self.caption_generator.generate(article, extraction)
                image = self.image_generator.generate(extraction, caption=caption)
                final_score = self.scorer.score(article, extraction, image=image).to_dict()
                artifacts = PipelineArtifacts(
                    article=article,
                    person=extraction.get("person", {}),
                    market=market,
                    extraction=extraction,
                    caption=caption,
                    image=image,
                    fetch_mode=fetched.mode,
                    fetch_errors=fetched.errors + market.get("errors", []) + run_errors,
                    score=final_score,
                    improvements=improvements,
                    skipped_regeneration=skipped_regeneration,
                )
            except Exception as exc:  # noqa: BLE001
                run_errors.append(f"attempt_{attempt}_failed: {exc}")
                run_errors.append(traceback.format_exc(limit=2))
                extraction = self.extractor.extract(article)
                extraction["market"] = market
                caption = self._fallback_caption(article, market)
                image = self.image_generator.generate(extraction, caption=caption)
                artifacts = PipelineArtifacts(
                    article=article,
                    person=extraction.get("person", {}),
                    market=market,
                    extraction=extraction,
                    caption=caption,
                    image=image,
                    fetch_mode=fetched.mode,
                    fetch_errors=fetched.errors + market.get("errors", []) + run_errors,
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
            extraction["market"] = market
            if best_artifacts:
                best_artifacts.improvements.extend(change for change in improve_changes if change not in best_artifacts.improvements)

        assert best_artifacts is not None
        self._restore_latest_image(best_artifacts)
        self.latest_text_path.write_text(best_artifacts.caption, encoding="utf-8")
        payload = {
            "generated_at": self._timestamp(),
            "person": best_artifacts.person,
            "article": {
                "title": best_artifacts.article.get("title", ""),
                "summary": best_artifacts.article.get("summary", ""),
                "url": best_artifacts.article.get("url", ""),
                "source": best_artifacts.article.get("source", ""),
                "published_at": best_artifacts.article.get("published_at", ""),
            },
            "market": {
                "btc_price": best_artifacts.market.get("btc_price"),
                "btc_change_percent": best_artifacts.market.get("btc_change_percent"),
                "btc_direction": best_artifacts.market.get("btc_direction"),
                "source": best_artifacts.market.get("source"),
            },
            "result": best_artifacts.to_dict(),
            "history_length": len(history),
        }
        archive_paths = self._archive_final_outputs(best_artifacts, payload)
        payload["archive"] = archive_paths
        self._write_json(self.best_result_path, payload)
        return {
            "best_result_path": str(self.best_result_path),
            "latest_text_path": str(self.latest_text_path),
            "latest_image_path": best_artifacts.image.get("latest_path"),
            "fetch_mode": fetched.mode,
            "fetch_errors": fetched.errors + market.get("errors", []) + run_errors,
            "person": payload["person"],
            "article": payload["article"],
            "market": payload["market"],
            "result": best_artifacts.to_dict(),
            "history_length": len(history),
            "archive": archive_paths,
        }

    def _archive_final_outputs(self, artifacts: PipelineArtifacts, payload: Dict[str, Any]) -> Dict[str, str]:
        generated_at = artifacts.image.get("generated_at") or self._timestamp()
        try:
            stamp = datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
        except ValueError:
            stamp = datetime.now(timezone.utc)
        archive_dir = self.archive_root / stamp.strftime("%Y%m%d")
        archive_dir.mkdir(parents=True, exist_ok=True)
        suffix = stamp.strftime('%Y%m%dT%H%M%S%f')
        caption_path = archive_dir / f"caption_{suffix}.txt"
        result_path = archive_dir / f"result_{suffix}.json"
        caption_path.write_text(artifacts.caption, encoding="utf-8")
        self._write_json(result_path, payload)
        artifacts.image["archive_dir"] = str(archive_dir)
        return {
            "image": artifacts.image.get("path", ""),
            "caption": str(caption_path),
            "result": str(result_path),
        }

    @staticmethod
    def _fallback_caption(article: Dict[str, Any], market: Dict[str, Any]) -> str:
        source = article.get("source", "source")
        url = article.get("url", "")
        market_line = ""
        if market.get("btc_price") is not None and market.get("btc_change_percent") is not None:
            market_line = f"\nBTC ${market['btc_price']:,.2f} / {market['btc_change_percent']:+.2f}%"
        return f"これヤバい⚠️\n速報を整理中\n{article.get('title', 'Crypto alert')}{market_line}\n出典: {source} {url}\n※要約ベース。投資判断は自己責任。"

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
