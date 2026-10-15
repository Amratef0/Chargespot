"""Station model (Member 1's Station, merged with the fields Member 2's scheduler needs).

Kept from Member 1: class-level registry `all_stations`, add_charger, remove_charger, get_chargers,
casting_station_to_dict, sequential_search_by_name, filter_by_governorate, filter_stations_by_connector,
update_charger_status, get_availability_summary, save_to_json, load_from_json.

Changed: methods RAISE ChargeSpotError subclasses instead of printing (a Streamlit page cannot show
`print` output); the JSON path is configurable (it used the current folder, so it crashed when the app
was started from another folder); new optional fields `area`, `price_per_kwh`, `lat`, `lon`,
`open_hour`, `close_hour` (Member 2's `area`/`location`; here `address` plays the role of `location`).
"""
import json
from pathlib import Path

from models.charger import ALL_CONNECTORS, CHARGER_STATUSES
from models.exceptions import (ChargerInUseError, DuplicateIDError, InvalidStatusError,
                               NotFoundError, ValidationError)
from utils.validators import require_id

DEFAULT_PATH = Path(__file__).resolve().parents[1] / "data" / "stations.json"


class Station:
    all_stations = []
    storage_path = DEFAULT_PATH

    def __init__(self, station_id, name, governorate, address, area=None, price_per_kwh=6.0,
                 lat=None, lon=None, open_hour=0, close_hour=24):
        require_id("station", station_id)
        if not isinstance(name, str) or not 3 <= len(name.strip()) <= 100:
            raise ValidationError("Station name must contain 3 to 100 characters.")
        if not str(governorate).strip() or not str(address).strip():
            raise ValidationError("Governorate and address cannot be empty.")
        if not isinstance(price_per_kwh, (int, float)) or price_per_kwh <= 0:
            raise ValidationError("Price per kWh must be a positive number.")
        if not (isinstance(open_hour, int) and isinstance(close_hour, int) and 0 <= open_hour < close_hour <= 24):
            raise ValidationError("Opening hours must satisfy 0 <= open < close <= 24.")
        self.station_id = int(station_id)
        self.name = name.strip()
        self.governorate = str(governorate).strip()
        self.address = str(address).strip()
        self.area = (area or self.governorate).strip()
        self.price_per_kwh = float(price_per_kwh)
        self.lat, self.lon = lat, lon
        self.open_hour, self.close_hour = open_hour, close_hour
        self.chargers = []

    # ----------------------------------------------------------- chargers
    def find_charger(self, charger_id):
        for c in self.chargers:
            if c["charger_id"] == charger_id:
                return c
        return None

    def add_charger(self, charger_object):
        if self.find_charger(charger_object.charger_id) is not None:
            raise DuplicateIDError(f"Charger ID {charger_object.charger_id} already exists in this station.")
        self.chargers.append(charger_object.casting_charge_to_dict())
        Station.save_to_json()
        return True

    def remove_charger(self, charger_id):
        c = self.find_charger(charger_id)
        if c is None:
            raise NotFoundError(f"Charger {charger_id} not found.")
        if c.get("charger_status") == "Occupied":
            raise ChargerInUseError(f"Cannot delete charger {charger_id} because it is currently Occupied.")
        self.chargers.remove(c)
        Station.save_to_json()
        return True

    def get_chargers(self):
        return self.chargers

    def usable_chargers(self, connector=None):
        """Chargers that can take bookings (not in Maintenance), optionally with a given connector."""
        return [c for c in self.chargers if c.get("charger_status") != "Maintenance"
                and (connector is None or c.get("connector_type") == connector)]

    @property
    def status(self):
        """Station-level status used by Member 2's scheduler."""
        return "Available" if self.usable_chargers() else "Unavailable"

    def update_charger_status(self, charger_id, new_status):
        if new_status not in CHARGER_STATUSES:
            raise InvalidStatusError(f"Invalid status. Choose from: {list(CHARGER_STATUSES)}")
        c = self.find_charger(charger_id)
        if c is None:
            raise NotFoundError("Charger ID not found in this station.")
        c["charger_status"] = new_status
        Station.save_to_json()
        return True

    def get_availability_summary(self):
        count = lambda s: sum(1 for ch in self.chargers if ch.get("charger_status") == s)
        return {"station_name": self.name, "total": len(self.chargers), "available": count("Available"),
                "occupied": count("Occupied"), "maintenance": count("Maintenance")}

    # ----------------------------------------------------------- serialisation
    def casting_station_to_dict(self):
        return {"station_id": self.station_id, "name": self.name, "governorate": self.governorate,
                "address": self.address, "area": self.area, "price_per_kwh": self.price_per_kwh,
                "lat": self.lat, "lon": self.lon, "open_hour": self.open_hour,
                "close_hour": self.close_hour, "chargers": self.chargers}

    @staticmethod
    def from_dict(s):
        st = Station(s["station_id"], s["name"], s["governorate"], s["address"], s.get("area"),
                     s.get("price_per_kwh", 6.0), s.get("lat"), s.get("lon"),
                     s.get("open_hour", 0), s.get("close_hour", 24))
        st.chargers = s.get("chargers", [])
        return st

    # ----------------------------------------------------------- search / filter (Member 1)
    @staticmethod
    def sequential_search_by_name(station_name, stations=None):
        """Sequential (linear) search: names are not sorted, so every station is checked."""
        target = station_name.strip().lower()
        return [s for s in (Station.all_stations if stations is None else stations) if target in s.name.lower()]

    @staticmethod
    def filter_by_governorate(governorate_name, stations=None):
        target = governorate_name.strip().lower()
        return [s for s in (Station.all_stations if stations is None else stations)
                if target == s.governorate.strip().lower()]

    @staticmethod
    def filter_stations_by_connector(connector_type, stations=None):
        target = connector_type.strip().lower()
        return [s for s in (Station.all_stations if stations is None else stations)
                if any(target == c.get("connector_type", "").strip().lower() for c in s.chargers)]

    @staticmethod
    def filter_stations_by_status(status, stations=None):
        return [s for s in (Station.all_stations if stations is None else stations)
                if any(c.get("charger_status") == status for c in s.chargers)]

    @staticmethod
    def filter_stations_by_min_power(min_kw, stations=None):
        return [s for s in (Station.all_stations if stations is None else stations)
                if any(c.get("charger_power_kw", 0) >= min_kw for c in s.chargers)]

    @staticmethod
    def save_to_json(filename=None):
        path = Path(filename or Station.storage_path)
        data = [s.casting_station_to_dict() for s in Station.all_stations]
        tmp = path.with_suffix(".tmp")                       # atomic: write temp file, then rename
        tmp.write_text(json.dumps(data, indent=4), encoding="utf-8")
        tmp.replace(path)

    @staticmethod
    def load_from_json(filename=None):
        path = Path(filename or Station.storage_path)
        Station.all_stations = [Station.from_dict(s) for s in json.loads(path.read_text(encoding="utf-8"))]
        return Station.all_stations
