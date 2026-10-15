class Scheduler:
    def __init__(self, distances):
        self.distances = distances

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

    def find_suitable_stations(self, driver_area, stations, start_time, end_time, booking_service):
        station_options = []
        for station in stations:
            if station.status == "Available":
                distance = self.get_distance(driver_area, station.location)
                if distance is not None:
                    conflict = booking_service.check_booking_overlap(station.station_id, start_time, end_time)
                    station_options.append({"station": station, "distance": distance, "is_available": not conflict})

        # Available stations first, then booked stations; nearest first in each group.
        for i in range(len(station_options)):
            for j in range(i + 1, len(station_options)):
                first = station_options[i]
                second = station_options[j]
                should_swap = False
                if second["is_available"] and not first["is_available"]:
                    should_swap = True
                elif second["is_available"] == first["is_available"] and second["distance"] < first["distance"]:
                    should_swap = True
                if should_swap == True:
                    station_options[i], station_options[j] = station_options[j], station_options[i]
        return station_options

    def find_best_station(station_options):
        for option in station_options:
            if option["is_available"]:
                return option
        return None


    def display_station_options(self, station_options, best_station):
        print("Stations ordered by availability and distance:")
        for i in range(len(station_options)):
            option = station_options[i]
            station = option["station"]

            if option["is_available"]:
                status = "Available"
            else:
                status = "Booked - Waiting List"

            if option == best_station:
                print(i + 1, "-", station.name, "-", option["distance"], "km -", status, "<-- Recommended")
            else:
                print(i + 1, "-", station.name, "-", option["distance"], "km -", status)
