from __future__ import annotations

import json
import sys
from pathlib import Path


def main() -> None:
    output_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("ci_output")
    required = [
        output_dir / "latest.png",
        output_dir / "latest.txt",
        output_dir / "best_result.json",
    ]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise SystemExit(f"Missing generated artifacts: {missing}")

    payload = json.loads((output_dir / "best_result.json").read_text(encoding="utf-8"))
    result = payload.get("result", {})
    latest_text = (output_dir / "latest.txt").read_text(encoding="utf-8")
    if result.get("caption") != latest_text:
        raise SystemExit("latest.txt does not match best_result.json caption")
    if result.get("image", {}).get("latest_path") != str(output_dir / "latest.png"):
        raise SystemExit("best_result.json latest_path does not point to latest.png")

    print("Artifacts verified:", ", ".join(str(path) for path in required))


if __name__ == "__main__":
    main()
