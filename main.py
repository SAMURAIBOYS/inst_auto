from __future__ import annotations

import argparse
import json
from pathlib import Path

from auto_loop import AutoImprovementLoop


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a buzz-ready crypto caption and image from the latest news.")
    parser.add_argument("--output-dir", type=Path, default=Path("output"), help="Directory to write latest.png, latest.txt, and best_result.json.")
    args = parser.parse_args()

    loop = AutoImprovementLoop(output_dir=args.output_dir)
    result = loop.run()
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
