import json

class Station:
    all_stations = []
    def __init__(self, station_id, name, governorate, address):
        self.station_id = station_id
        self.name = name
        self.governorate = governorate
        self.address = address
        self.chargers = []

    def add_charger(self, charger_object):
        for charger in self.chargers:
            if charger["charger_id"] == charger_object.charger_id:
                print("Charger ID already exists.")
                return False
        charger_dict = charger_object.casting_charge_to_dict()
        self.chargers.append(charger_dict)
        print("Charger added successfully to the station.")
        Station.save_to_json()
        return True

    def remove_charger(self, charger_id):
        for charger in self.chargers:
            if charger["charger_id"] == charger_id:
                if charger.get("charger_status") == "Occupied":
                    print(f"Cannot delete charger {charger_id} because it is currently Occupied!")
                    return False
                self.chargers.remove(charger)
                print("Charger removed successfully.")
                Station.save_to_json()
                return True
        print("Charger ID not found.")
        return False

    def get_chargers(self):
        return self.chargers

    def casting_station_to_dict(self):
        return {
            "station_id": self.station_id,
            "name": self.name,
            "governorate": self.governorate,
            "address": self.address,
            "chargers": self.chargers
        }

    @staticmethod
    def sequential_search_by_name(station_name):
        results = []
        target = station_name.strip().lower()

        for station in Station.all_stations:
            if target in station.name.lower():
                results.append(station)
        return results

    @staticmethod
    def filter_by_governorate(governorate_name):
        results = []
        target = governorate_name.strip().lower()

        for station in Station.all_stations:
            if target == station.governorate.strip().lower():
                results.append(station)
        return results

    @staticmethod
    def filter_stations_by_connector(connector_type):
        results = []
        target = connector_type.strip().lower()

        for station in Station.all_stations:
            for charger in station.chargers:
                if target == charger.get("connector_type", "").strip().lower():
                    results.append(station)
                    break
        return results

    def update_charger_status(self, charger_id, new_status):
        valid_statuses = ["Available", "Occupied", "Maintenance"]
        if new_status not in valid_statuses:
            print(f"Invalid status. Choose from: {valid_statuses}")
            return False

        for charger in self.chargers:
            if charger["charger_id"] == charger_id:
                charger["charger_status"] = new_status
                print(f"Charger {charger_id} status updated to '{new_status}' successfully.")
                Station.save_to_json()
                return True

        print("Charger ID not found in this station.")
        return False

    def get_availability_summary(self):

        total_chargers = len(self.chargers)
        available_count = sum(1 for ch in self.chargers if ch.get("charger_status") == "Available")
        occupied_count = sum(1 for ch in self.chargers if ch.get("charger_status") == "Occupied")
        maintenance_count = sum(1 for ch in self.chargers if ch.get("charger_status") == "Maintenance")

        station_summary = {
            "station_name": self.name,
            "total": total_chargers,
            "available": available_count,
            "occupied": occupied_count,
            "maintenance": maintenance_count
        }
        return station_summary

    @staticmethod
    def save_to_json(filename='stations.json'):
        stations_data = [station.casting_station_to_dict() for station in Station.all_stations]
        with open(filename, 'w') as file:
            json.dump(stations_data, file, indent=4)
        print("All stations saved successfully.")
    @staticmethod
    def load_from_json():
        with open('stations.json', 'r') as file:
            stations = json.load(file)
            Station.all_stations = []

            for s in stations:
                new_station = Station(
                    s['station_id'],
                    s['name'],
                    s['governorate'],
                    s['address']
                )
                new_station.chargers = s['chargers']
                Station.all_stations.append(new_station)
        print("Stations loaded successfully.")