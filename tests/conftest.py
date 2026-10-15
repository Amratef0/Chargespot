import shutil
from datetime import datetime
from pathlib import Path

import pandas as pd
import pytest

from data.generate_data import generate_all, load_catalog, make_messy, simulate

ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 3, 2, 9, 0)            # "today" for the tests: just after the small history ends


@pytest.fixture(scope="session")
def small():
    """Small, fast, deterministic simulated history on the TEAM's station catalog (35 days)."""
    return simulate(seed=7, n_days=35, end_date="2026-02-28", n_drivers=80, base_requests=6,
                    catalog=load_catalog(ROOT / "data" / "stations.json"))


@pytest.fixture(scope="session")
def messy(small):
    return make_messy(small["bookings"], seed=7, n_rows=1500, defect_rate=0.02)


@pytest.fixture(scope="session")
def _template_dir(tmp_path_factory):
    d = tmp_path_factory.mktemp("template")
    for f in ("stations.json", "distances.json"):
        shutil.copy(ROOT / "data" / f, d / f)
    generate_all(out_dir=d, n_days=14, end_date="2026-02-28", n_drivers=40, base_requests=4)
    return d


@pytest.fixture()
def data_dir(_template_dir, tmp_path):
    """A private copy of a tiny but complete data folder (tests may modify it freely)."""
    dst = tmp_path / "data"
    shutil.copytree(_template_dir, dst)
    return dst


@pytest.fixture()
def ctx(data_dir):
    from core.app_context import ChargeSpotApp
    from services.mailer import MemoryMailer
    return ChargeSpotApp(data_dir, now_fn=lambda: NOW, mailer=MemoryMailer())


def mk_bookings(rows):
    """rows: (booking_id, station, start 'YYYY-mm-dd HH:MM', duration, status, queued, wait)"""
    df = pd.DataFrame(rows, columns=["booking_id", "station_id", "start_time", "duration_min",
                                     "status", "queued", "wait_min"])
    df["start_time"] = pd.to_datetime(df["start_time"])
    df["connector"] = "CCS2"
    return df
