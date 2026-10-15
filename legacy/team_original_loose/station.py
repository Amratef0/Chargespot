class Station:
    def __init__(self, station_id, name, area, location, city, status, available_slots):
        self.station_id = station_id
        self.name = name
        self.area = area
        self.location = location
        self.city = city
        self.status = status
        self.available_slots = available_slots

    def display_slots(self):
        print("\nAvailable Slots:")
        if len(self.available_slots) == 0:
            print("No available slots.")
            return
        for i in range(len(self.available_slots)):
            print(i + 1, "-", self.available_slots[i])
