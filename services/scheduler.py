from algorithms.greedy_scheduler import pick_charger_greedy, suggest_alternatives
from algorithms.sorting import merge_sort


class Scheduler:
    def __init__(self, distances):
        self.distances = distances

    @staticmethod
    def get_areas(stations):
        areas = []
        for station in stations:
            if station.area not in areas:
                areas.append(station.area)
        return areas

    def get_distance(self, driver_area, station_location):
        if driver_area in self.distances and station_location in self.distances[driver_area]:
            return self.distances[driver_area][station_location]
        return None

    def find_suitable_stations(self, driver_area, stations, connector, start, duration_min, booking_service):
        day, s = start.strftime("%Y-%m-%d"), start.hour * 60 + start.minute
        options = []
        for station in stations:
            usable = station.usable_chargers(connector)
            if station.status != "Available" or not usable:
                continue
            distance = self.get_distance(driver_area, station.address)
            if distance is None:
                continue
            busy_of = lambda cid, st=station: booking_service.busy_intervals(cid, day)
            close = station.close_hour * 60
            slot = pick_charger_greedy(usable, busy_of, s, duration_min, close, max_shift=0)
            alts = [] if slot else suggest_alternatives(usable, busy_of, s, duration_min, close, n=3)
            options.append({"station": station, "distance": distance, "is_available": slot is not None,
                            "charger_id": slot.charger_id if slot else None, "alternatives": alts})
        ordered, _ = merge_sort(options, key=lambda o: (not o["is_available"], o["distance"]))
        return ordered

    @staticmethod
    def find_best_station(station_options):
        for option in station_options:
            if option["is_available"]:
                return option
        return None
