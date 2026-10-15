class Booking:
    def __init__(self, booking_id, driver_id, station_id, station_name, area, start_time, end_time, status):
        self.booking_id = booking_id
        self.driver_id = driver_id
        self.station_id = station_id
        self.station_name = station_name
        self.area = area
        self.start_time = start_time
        self.end_time = end_time
        self.status = status
