from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from auto_loop import AutoImprovementLoop


def _configure_stdio_for_utf8() -> None:
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(encoding="utf-8", errors="backslashreplace")
            except ValueError:
                pass


def main() -> None:
    _configure_stdio_for_utf8()
    parser = argparse.ArgumentParser(description="Generate a crypto social post from real news with resilient fallbacks.")
    parser.add_argument("--output-dir", type=Path, default=Path("output"), help="Directory to write latest.png, latest.txt, and best_result.json.")
    args = parser.parse_args()

    loop = AutoImprovementLoop(output_dir=args.output_dir)
    result = loop.run()
    artifacts = result.get("result", {})
    extraction = artifacts.get("extraction", {})
    article = artifacts.get("article", {})
    person = extraction.get("person", {})
    market = extraction.get("market") or article.get("market", {})

    payload = {
        **result,
        "person": {"name": person.get("name", ""), "role": person.get("role", ""), "summary": person.get("summary", "")},
        "article": {
            "title": article.get("title", ""),
            "summary": article.get("summary", ""),
            "url": article.get("url", ""),
            "source": article.get("source", ""),
            "published_at": article.get("published_at", ""),
            "image_url": article.get("image_url", ""),
        },
        "market": {
            "btc_price": market.get("btc_price"),
            "btc_change_percent": market.get("btc_change_percent"),
            "btc_direction": market.get("btc_direction"),
        },
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
