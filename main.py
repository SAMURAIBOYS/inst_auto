from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict

from auto_loop import AutoImprovementLoop


def load_source(path: Path | None) -> Dict[str, Any]:
    if path is None:
        return {
            "title": "Ada Lovelace and Alan Turing inspire a new wave of trustworthy AI design",
            "summary": (
                "A feature story highlights how Ada Lovelace and Alan Turing are used as reference points "
                "for explainability, reliability, and disciplined automation in modern AI systems."
            ),
            "people": ["Ada Lovelace", "Alan Turing"],
            "keywords": ["trustworthy AI", "automation", "explainability", "reliability"],
        }
    with path.open("r", encoding="utf-8") as fp:
        return json.load(fp)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the autonomous post-improvement loop.")
    parser.add_argument("--source", type=Path, default=None, help="Path to source JSON describing the original material.")
    parser.add_argument("--output-dir", type=Path, default=Path("."), help="Directory to write logs and best_result.json.")
    parser.add_argument("--max-attempts", type=int, default=5, help="Maximum number of regeneration attempts.")
    args = parser.parse_args()

    source = load_source(args.source)
    loop = AutoImprovementLoop(output_dir=args.output_dir, max_attempts=args.max_attempts)
    result = loop.run(source)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
