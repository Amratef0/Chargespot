
from __future__ import annotations

import os
import sys
from pathlib import Path


def load_env(path: Path | str | None = None) -> list[str]:
    """Load the file; returns the names it set. Missing file or running under pytest -> nothing happens."""
    if "pytest" in sys.modules:
        return []
    p = Path(path) if path else Path(__file__).resolve().parents[1] / ".env"
    try:
        lines = p.read_text(encoding="utf-8-sig").splitlines()
    except OSError:
        return []
    done = []
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip().removeprefix("export ").strip(), value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        if key and key not in os.environ:
            os.environ[key] = value
            done.append(key)
    return done