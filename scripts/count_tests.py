"""Print the real test total (avoids -q swallowing it)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    r = subprocess.run(
        [sys.executable, "-m", "pytest", str(root / "tests"), "--collect-only", "-q"],
        capture_output=True, text=True,
    )
    n = sum(1 for line in r.stdout.splitlines() if "::" in line)
    print(f"{n} tests collected")


if __name__ == "__main__":
    main()
