from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from auto_loop import AutoImprovementLoop
from generate_caption import CaptionGenerator


class CaptionGuardTests(unittest.TestCase):
    def test_long_url_caption_returns_within_limit(self) -> None:
        article = {
            "source": "very_long_source_name",
            "url": "https://example.com/" + ("very-long-path-segment-" * 20),
        }
        extraction = {
            "sentiment": "neutral",
            "topic": "Bitcoin関連ニュース",
            "claim_summary": "Bitcoin / Satoshi Nakamotoが注目テーマ。記事要点: " + ("A" * 200),
        }

        caption = CaptionGenerator().generate(article, extraction)

        self.assertLessEqual(len(caption), 180)
        self.assertIn("出典:", caption)
        self.assertIn("※要約ベース", caption)


class LatestArtifactConsistencyTests(unittest.TestCase):
    def test_latest_png_is_restored_to_winning_image(self) -> None:
        temp_dir = Path(tempfile.mkdtemp(prefix="insta_auto_ci_"))
        self.addCleanup(lambda: shutil.rmtree(temp_dir, ignore_errors=True))

        loop = AutoImprovementLoop(output_dir=temp_dir, max_attempts=2)

        class StubFetcher:
            def fetch_latest(self):
                class Result:
                    article = {
                        "title": "Bitcoin ETF headline",
                        "summary": "Bitcoin momentum stays in focus.",
                        "url": "https://example.com/news",
                        "published_at": "2026-03-23T00:00:00+00:00",
                        "source": "stub_source",
                    }
                    mode = "sample"
                    errors = []

                return Result()

        class StubScorer:
            def __init__(self) -> None:
                self.calls = 0

            def score(self, article, extraction, image=None):
                self.calls += 1
                total = 0.8 if self.calls == 2 else 0.4 if self.calls == 4 else 0.5
                return type(
                    "Score",
                    (),
                    {
                        "to_dict": lambda self2: {
                            "change_score": 0.5,
                            "topic_score": 0.5,
                            "people_score": 0.8,
                            "total_score": total,
                            "should_generate": True,
                            "diagnostics": {},
                        }
                    },
                )()

        loop.fetcher = StubFetcher()
        loop.scorer = StubScorer()

        result = loop.run()
        best_path = Path(result["result"]["image"]["path"])
        latest_path = Path(result["latest_image_path"])
        best_result_path = Path(result["best_result_path"])
        latest_text_path = Path(result["latest_text_path"])

        self.assertTrue(best_path.exists())
        self.assertTrue(latest_path.exists())
        self.assertTrue(best_result_path.exists())
        self.assertTrue(latest_text_path.exists())

        best_hash = hashlib.sha256(best_path.read_bytes()).hexdigest()
        latest_hash = hashlib.sha256(latest_path.read_bytes()).hexdigest()
        self.assertEqual(best_hash, latest_hash)

        saved = json.loads(best_result_path.read_text(encoding="utf-8"))
        self.assertEqual(saved["result"]["caption"], latest_text_path.read_text(encoding="utf-8"))
        self.assertEqual(saved["result"]["image"]["latest_path"], str(latest_path))


class ImageLayoutGuardTests(unittest.TestCase):
    def test_generated_image_has_expected_master_layout(self) -> None:
        temp_dir = Path(tempfile.mkdtemp(prefix="insta_auto_layout_"))
        self.addCleanup(lambda: shutil.rmtree(temp_dir, ignore_errors=True))
        loop = AutoImprovementLoop(output_dir=temp_dir, max_attempts=1)
        result = loop.run()
        latest_path = Path(result["latest_image_path"])
        data = latest_path.read_bytes()
        self.assertEqual(data[:8], b"\x89PNG\r\n\x1a\n")
        width = int.from_bytes(data[16:20], "big")
        height = int.from_bytes(data[20:24], "big")
        self.assertEqual((width, height), (1080, 1080))



if __name__ == "__main__":
    unittest.main()
