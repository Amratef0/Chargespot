

class Booking:
    def __init__(self, booking_id, driver_id, station_id, station_name, area, start_time, end_time, status,
                 charger_id=None, connector=None, created_at=None, queued=0, wait_min=0):
        self.booking_id = booking_id
        self.driver_id = driver_id
        self.station_id = station_id
        self.station_name = station_name
        self.area = area
        self.start_time = start_time          # datetime
        self.end_time = end_time              # datetime
        self.status = status                  # Confirmed | Cancelled | Completed | No-Show
        self.charger_id = charger_id
        self.connector = connector
        self.created_at = created_at
        self.queued = queued                  # 1 if the driver waited in the waiting list first
        self.wait_min = wait_min

    @property
    def duration_min(self):
        return int((self.end_time - self.start_time).total_seconds() // 60)
