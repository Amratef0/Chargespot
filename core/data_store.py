"""File helpers (Member 4): paths, atomic CSV writing, first-run dataset creation."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pandas as pd

from core.env import load_env
from core.schema import DATETIME_FORMAT

load_env()                      # reads <project>/.env BEFORE anything below looks at os.environ
ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = Path(os.environ.get("CHARGESPOT_DATA_DIR", ROOT / "data"))

HISTORY_FILES = ("bookings", "sessions", "drivers", "vehicles", "charger_health")


def atomic_write_csv(df: pd.DataFrame, path: Path | str) -> None:
    """Save df to CSV safely (temp file + rename): a crash while saving cannot corrupt the file."""
    path = Path(path)
    df = df.copy()
    for c in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[c]):
            df[c] = df[c].dt.strftime(DATETIME_FORMAT)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    os.close(fd)
    try:
        df.to_csv(tmp, index=False)
        os.replace(tmp, path)
    except Exception:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise


def ensure_dataset(data_dir: Path | str = DATA_DIR) -> None:
    """Create the simulated history on first run (stations.json is the team's own file)."""
    d = Path(data_dir)
    if not (d / "stations.json").exists():
        from data.build_catalog import build
        build()
    if not all((d / f"{n}.csv").exists() for n in HISTORY_FILES):
        from data.generate_data import generate_all
        generate_all(out_dir=d)


def load_health_truth(data_dir: Path | str = DATA_DIR):
    p = Path(data_dir) / "charger_health_truth.csv"
    return pd.read_csv(p) if p.exists() else None


def messy_path(data_dir: Path | str = DATA_DIR) -> Path:
    return Path(data_dir) / "bookings_messy.csv"