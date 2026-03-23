from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> None:
    for requirement_file in ("requirements.txt", "requirements-dev.txt"):
        path = Path(requirement_file)
        if path.exists():
            subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", str(path)])
            print(f"Installed dependencies from {path}")
        else:
            print(f"Skipped missing {path}")


if __name__ == "__main__":
    main()
