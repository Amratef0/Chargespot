"""Station service (Member 1's station_service, extended).

Kept: Stack-based undo, `remove_charger_with_undo`, `undo_last_admin_action`.
Added: the undo Stack now covers EVERY admin change (it only covered charger removal), station
add/edit/remove, a HashTable ID registry (instant lookup of a station or charger by ID), and the rule
"a charger/station with active bookings cannot be removed" (only the Occupied status was checked).
The stack and registry are per service instance (they were a module-level global).
"""
from algorithms.hash_table import HashTable
from algorithms.stack import Stack
from models.charger import charger_from_dict
from models.exceptions import ChargerInUseError, DuplicateIDError, NotFoundError, ValidationError
from models.station import Station
from utils.validators import require_id


class StationService:
    def __init__(self, path, has_active_bookings=lambda charger_id: False):
        Station.storage_path = path
        Station.load_from_json()
        self.has_active_bookings = has_active_bookings
        self.admin_stack = Stack()
        self.station_index = HashTable(64)
        self.charger_index = HashTable(128)
        self.rebuild_registry()

    # ------------------------------------------------------------ registry (hash table)
    def rebuild_registry(self):
        self.station_index = HashTable(64)
        self.charger_index = HashTable(128)
        for s in Station.all_stations:
            self.station_index.put(s.station_id, s)
            for c in s.chargers:
                self.charger_index.put(c["charger_id"], (s, c))

    @property
    def stations(self):
        return Station.all_stations

    def get_station(self, station_id):
        s = self.station_index.get(int(station_id)) if str(station_id).isdigit() else None
        if s is None:
            raise NotFoundError(f"Station {station_id} not found.")
        return s

    def get_charger(self, charger_id):
        """-> (station, charger_dict) in O(1) average through the hash registry."""
        hit = self.charger_index.get(charger_id)
        if hit is None:
            raise NotFoundError(f"Charger {charger_id} not found.")
        return hit

    # ------------------------------------------------------------ admin actions (all undoable)
    def add_station(self, station_id, name, governorate, address, area=None, price_per_kwh=6.0, lat=None, lon=None):
        require_id("station", station_id)
        if self.station_index.contains(int(station_id)):
            raise DuplicateIDError(f"Station ID {station_id} already exists.")
        s = Station(station_id, name, governorate, address, area, price_per_kwh, lat, lon)
        Station.all_stations.append(s)
        self.admin_stack.push({"action": "add_station", "station": s})
        self._saved()
        return s

    def edit_station(self, station_id, **fields):
        s = self.get_station(station_id)
        allowed = {"name", "governorate", "address", "area", "price_per_kwh"}
        bad = set(fields) - allowed
        if bad:
            raise ValidationError("Cannot edit: " + ", ".join(bad))
        old = {k: getattr(s, k) for k in fields}
        probe = Station(s.station_id, **{**{"name": s.name, "governorate": s.governorate, "address": s.address,
                                            "area": s.area, "price_per_kwh": s.price_per_kwh}, **fields})   # validates
        for k in fields:
            setattr(s, k, getattr(probe, k))
        self.admin_stack.push({"action": "edit_station", "station": s, "old": old})
        self._saved()
        return s

    def remove_station(self, station_id):
        s = self.get_station(station_id)
        for c in s.chargers:
            if c.get("charger_status") == "Occupied" or self.has_active_bookings(c["charger_id"]):
                raise ChargerInUseError(f"Cannot remove {s.name}: charger {c['charger_id']} is occupied or has active bookings.")
        idx = Station.all_stations.index(s)
        Station.all_stations.remove(s)
        self.admin_stack.push({"action": "remove_station", "station": s, "index": idx})
        self._saved()
        return True

    def add_charger(self, station_id, charger_object):
        s = self.get_station(station_id)
        if self.charger_index.contains(charger_object.charger_id):
            raise DuplicateIDError(f"Charger ID {charger_object.charger_id} already exists in the network.")
        s.add_charger(charger_object)
        self.admin_stack.push({"action": "add_charger", "station": s, "charger_id": charger_object.charger_id})
        self.rebuild_registry()
        return True

    def remove_charger_with_undo(self, station, charger_id):
        c = station.find_charger(charger_id)
        if c is None:
            raise NotFoundError(f"Charger {charger_id} not found.")
        if c.get("charger_status") == "Occupied":
            raise ChargerInUseError(f"Cannot delete charger {charger_id} because it is currently Occupied.")
        if self.has_active_bookings(charger_id):
            raise ChargerInUseError(f"Cannot delete charger {charger_id}: it has active bookings. Cancel them first.")
        index = station.chargers.index(c)
        station.remove_charger(charger_id)
        self.admin_stack.push({"action": "remove_charger", "station": station, "charger_data": c, "index": index})
        self.rebuild_registry()
        return True

    def update_charger_status(self, station, charger_id, new_status, record=True):
        c = station.find_charger(charger_id)
        old = c["charger_status"] if c else None
        station.update_charger_status(charger_id, new_status)
        if record:
            self.admin_stack.push({"action": "status", "station": station, "charger_id": charger_id, "old": old})
        return True

    def undo_last_admin_action(self):
        """Undo the most recent admin change. Returns a message, or None if there is nothing to undo."""
        a = self.admin_stack.pop()
        if a is None:
            return None
        s, act = a["station"], a["action"]
        if act == "add_station":
            Station.all_stations.remove(s); msg = f"Undid: station '{s.name}' removed again."
        elif act == "remove_station":
            Station.all_stations.insert(a["index"], s); msg = f"Undid: station '{s.name}' restored."
        elif act == "edit_station":
            for k, v in a["old"].items():
                setattr(s, k, v)
            msg = f"Undid: edit of station '{s.name}'."
        elif act == "add_charger":
            c = s.find_charger(a["charger_id"])
            if c is not None:
                s.chargers.remove(c)
            msg = f"Undid: charger {a['charger_id']} removed from {s.name}."
        elif act == "remove_charger":
            cd = a["charger_data"]
            if self.charger_index.contains(cd["charger_id"]):
                self.admin_stack.push(a)                                  # cannot restore: ID reused meanwhile
                raise DuplicateIDError(f"Cannot undo: charger ID {cd['charger_id']} exists again.")
            s.chargers.insert(a["index"], cd)
            msg = f"Undid: charger {cd['charger_id']} restored to {s.name}."
        elif act == "status":
            s.find_charger(a["charger_id"])["charger_status"] = a["old"]
            msg = f"Undid: status of {a['charger_id']} back to {a['old']}."
        else:
            return None
        Station.save_to_json()
        self.rebuild_registry()
        return msg

    def _saved(self):
        Station.save_to_json()
        self.rebuild_registry()

    # ------------------------------------------------------------ search / filter (delegates to Station)
    def search(self, name="", governorate=None, connector=None, status=None, min_kw=None):
        res = Station.sequential_search_by_name(name) if name.strip() else list(Station.all_stations)
        if governorate:
            res = Station.filter_by_governorate(governorate, res)
        if connector:
            res = Station.filter_stations_by_connector(connector, res)
        if status:
            res = Station.filter_stations_by_status(status, res)
        if min_kw:
            res = Station.filter_stations_by_min_power(min_kw, res)
        return res

    @staticmethod
    def charger_objects(station):
        """Chargers as ACCharger / DCCharger objects (polymorphism: each prints its own info)."""
        return [charger_from_dict(c) for c in station.chargers]
