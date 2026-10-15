"""Tiny JSON file helpers shared by the auth stores (atomic write: a crash cannot corrupt the file)."""
import json
import os
import tempfile
from pathlib import Path


def read_json(path, default):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def write_json_atomic(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp, path)
        try:
            os.chmod(path, 0o600)            # secrets-adjacent files: owner only (ignored on Windows)
        except OSError:
            pass
    except Exception:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise
