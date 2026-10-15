from booking import Booking

class BookingService:
    def __init__(self):
        self.bookings = []

    def time_to_minutes(time):
        return int(time[:2]) * 60 + int(time[3:])

    def is_overlap(start1, end1, start2, end2):
        return start1 == start2 and end1 == end2

    def check_booking_overlap(self, station_id, start_time, end_time):
        new_start = BookingService.time_to_minutes(start_time)
        new_end = BookingService.time_to_minutes(end_time)
        for booking in self.bookings:
            if booking.station_id == station_id and booking.status == "Confirmed":
                old_start = BookingService.time_to_minutes(booking.start_time)
                old_end = BookingService.time_to_minutes(booking.end_time)
                if BookingService.is_overlap(new_start, new_end, old_start, old_end):
                    return True
        return False

    def create_booking(self, driver_id, station, start_time, end_time):
        booking_id = 1
        for booking in self.bookings:
            if booking.booking_id >= booking_id:
                booking_id = booking.booking_id + 1
        booking = Booking(booking_id, driver_id, station.station_id, station.name, station.area, start_time, end_time, "Confirmed")
        self.bookings.append(booking)
        if start_time in station.available_slots:
            station.available_slots.remove(start_time)
        return booking

    def try_booking(self, driver_id, station, start_time, end_time, waiting_queue):
        conflict = self.check_booking_overlap(station.station_id, start_time, end_time)
        if conflict:
            print("\nThe selected time is already booked.")
            request = waiting_queue.add_to_waiting_list(driver_id, station.station_id, start_time, end_time)
            print("You have been added to the waiting list.")
            print("Waiting Request ID:", request["request_id"])
            return False
        booking = self.create_booking(driver_id, station, start_time, end_time)
        print("\nBooking Confirmed!")
        print("Booking ID:", booking.booking_id)
        print("Driver ID:", booking.driver_id)
        print("Station:", booking.station_name)
        print("Area:", booking.area)
        print("Start Time:", booking.start_time)
        print("End Time:", booking.end_time)
        print("Status:", booking.status)
        return True

    def cancel_booking(self, booking_id):
        for booking in self.bookings:
            if booking.booking_id == booking_id and booking.status == "Confirmed":
                booking.status = "Cancelled"
                return booking
        return None
