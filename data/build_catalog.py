"""One-off builder: merges the team's two station catalogs into data/stations.json + data/distances.json.

Inputs (original team files, kept in legacy/):
  * station_data.py  (Member 2): 15 stations with area/location/city + the distance matrix
  * stations.json    (Member 1): 1 station ("Tahrir EV Station") WITH chargers
Output: 16 stations in Member 1's model (governorate/address/chargers) + Member 2's `area`.

Added by Member 4 (clearly extra data, not from the team): chargers for stations 2-16, price per kWh,
and APPROXIMATE coordinates (for the map only; not surveyed).
Run:  python -m data.build_catalog
"""
import json
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEG = ROOT / "legacy" / "team_original_zip"
OUT = ROOT / "data"

# (type, connector, kW) per station id. Station 1 keeps Member 1's own two chargers.
PLAN = {
    2: [("DC", "CCS2", 120), ("DC", "CCS2", 60), ("AC", "Type 2", 22), ("AC", "Type 2", 11)],
    3: [("DC", "CCS2", 120), ("DC", "CHAdeMO", 50), ("AC", "Type 2", 22)],
    4: [("DC", "CCS2", 60), ("AC", "Type 2", 22), ("AC", "Type 2", 11)],
    5: [("DC", "CCS2", 120), ("DC", "CCS2", 60), ("DC", "CHAdeMO", 50), ("AC", "Type 2", 22), ("AC", "Type 2", 11)],
    6: [("DC", "CCS2", 60), ("AC", "Type 2", 22)],
    7: [("DC", "CCS2", 60), ("AC", "Type 2", 22), ("AC", "Type 2", 7)],
    8: [("DC", "CCS2", 60), ("AC", "Type 2", 11)],
    9: [("DC", "CCS2", 150), ("DC", "CCS2", 120), ("DC", "CHAdeMO", 50), ("AC", "Type 2", 22), ("AC", "Type 2", 22)],
    10: [("DC", "CCS2", 120), ("DC", "CCS2", 60), ("AC", "Type 2", 22), ("AC", "Type 2", 11)],
    11: [("DC", "CCS2", 120), ("DC", "CHAdeMO", 50), ("AC", "Type 2", 22), ("AC", "Type 2", 11)],
    12: [("DC", "CCS2", 120), ("DC", "CCS2", 60), ("AC", "Type 2", 22), ("AC", "Type 2", 11)],
    13: [("DC", "CCS2", 150), ("DC", "CCS2", 120), ("DC", "CHAdeMO", 50), ("AC", "Type 2", 22), ("AC", "Type 2", 22)],
    14: [("DC", "CCS2", 120), ("DC", "CCS2", 60), ("AC", "Type 2", 22)],
    15: [("DC", "CCS2", 60), ("AC", "Type 2", 22), ("AC", "Type 2", 11)],
    16: [("DC", "CCS2", 120), ("DC", "CCS2", 60), ("AC", "Type 2", 22), ("AC", "Type 2", 11)],
}
MAINTENANCE = {"AC-108", "AC-114"}                     # two chargers out of service in the demo data
EXTRA = {   # id: (price EGP/kWh, lat, lon)  coordinates are APPROXIMATE (display only)
    1: (6.5, 30.0444, 31.2357), 2: (5.5, 31.2150, 29.9433), 3: (5.5, 31.2194, 29.9421),
    4: (5.0, 31.2335, 29.9490), 5: (6.0, 31.2457, 29.9675), 6: (5.0, 31.2690, 29.9990),
    7: (4.5, 31.2170, 29.9380), 8: (4.5, 31.2370, 29.9600), 9: (6.5, 30.0560, 31.3400),
    10: (6.0, 30.0630, 31.3460), 11: (7.0, 30.0880, 31.3250), 12: (7.5, 29.9600, 31.2580),
    13: (7.0, 30.0074, 31.4913), 14: (6.5, 30.0270, 31.4750), 15: (7.5, 30.0610, 31.2190),
    16: (6.5, 30.0480, 31.2400),
}


def _load_legacy_station_data():
    """Execute the team's station_data.py with a stand-in Station that accepts its 7 arguments."""
    stub = types.ModuleType("station")

    class Station:                     # the old 7-argument constructor Member 2 used
        def __init__(self, station_id, name, area, location, city, status, slots):
            self.station_id, self.name, self.area = station_id, name, area
            self.location, self.city = location, city

    stub.Station = Station
    sys.modules["station"] = stub
    ns = {}
    exec((LEG / "station_data.py").read_text(), ns)
    del sys.modules["station"]
    return ns["stations"], ns["distances"]


def build():
    old, distances = _load_legacy_station_data()
    m1 = json.loads((LEG / "stations.json").read_text())
    ac_n, dc_n, out = 102, 202, []
    for s in m1:                                                      # Member 1's station keeps its data
        d = dict(s)
        d.update(area="Downtown", price_per_kwh=EXTRA[s["station_id"]][0], lat=EXTRA[s["station_id"]][1],
                 lon=EXTRA[s["station_id"]][2], open_hour=0, close_hour=24)
        out.append(d)
    for s in old:
        chargers = []
        for ctype, conn, kw in PLAN[s.station_id]:
            if ctype == "AC":
                cid, ac_n = f"AC-{ac_n}", ac_n + 1
            else:
                cid, dc_n = f"DC-{dc_n}", dc_n + 1
            chargers.append({"charger_id": cid, "charger_power_kw": kw,
                             "charger_status": "Maintenance" if cid in MAINTENANCE else "Available",
                             "connector_type": conn, "type": ctype})
        p, la, lo = EXTRA[s.station_id]
        out.append({"station_id": s.station_id, "name": s.name.strip(), "governorate": s.city,
                    "address": s.location, "area": s.area, "price_per_kwh": p, "lat": la, "lon": lo,
                    "open_hour": 0, "close_hour": 24, "chargers": chargers})
    out.sort(key=lambda d: d["station_id"])
    (OUT / "stations.json").write_text(json.dumps(out, indent=4))
    (OUT / "distances.json").write_text(json.dumps(distances, indent=4))
    return out


if __name__ == "__main__":
    cat = build()
    print(len(cat), "stations,", sum(len(s["chargers"]) for s in cat), "chargers")
