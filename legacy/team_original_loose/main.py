from station_data import stations, distances
from scheduler import Scheduler
from booking_service import BookingService
from waiting_queue import WaitingQueue
from login_and_register import login, register_user

scheduler = Scheduler(distances)
booking_service = BookingService()
waiting_queue = WaitingQueue()

all_slots = [
    "00:00", "01:00", "02:00", "03:00", "04:00", "05:00",
    "06:00", "07:00", "08:00", "09:00", "10:00", "11:00",
    "12:00", "13:00", "14:00", "15:00", "16:00", "17:00",
    "18:00", "19:00", "20:00", "21:00", "22:00", "23:00"
]

driver_ids = {}
next_driver_number = 101


def get_driver_id(user):
    global next_driver_number
    email = user["email"]
    if email not in driver_ids:
        driver_ids[email] = "D" + str(next_driver_number)
        next_driver_number += 1
    return driver_ids[email]

areas = Scheduler.get_areas(stations)
def calculate_end_time(start_time):
    end_minutes = BookingService.time_to_minutes(start_time) + 60
    return str(end_minutes // 60).zfill(2) + ":" + str(end_minutes % 60).zfill(2)


def display_waiting_list():
    print("\nWaiting List:")
    if len(waiting_queue.queue) == 0:
        print("Waiting list is empty.")
        return
    for request in waiting_queue.queue:
        station_name = "Unknown station"
        for station in stations:
            if station.station_id == request["station_id"]:
                station_name = station.name
                break
        print("Request ID:", request["request_id"], "| Driver:", request["driver_id"], "| Station:", station_name,
              "| Time:", request["start_time"], "-", request["end_time"])


def display_all_bookings():
    print("\nBooking History:")
    if len(booking_service.bookings) == 0:
        print("No bookings found.")
        return
    for booking in booking_service.bookings:
        print("Booking ID:", booking.booking_id, "| Driver:", booking.driver_id, "| Station:", booking.station_name,
              "| Time:", booking.start_time, "-", booking.end_time, "| Status:", booking.status)


def display_my_bookings(driver_id):
    my_bookings = []
    for booking in booking_service.bookings:
        if booking.driver_id == driver_id:
            my_bookings.append(booking)
    print("\nYour Booking History:")
    if len(my_bookings) == 0:
        print("You do not have any bookings yet.")
        return
    for booking in my_bookings:
        print("Booking ID:", booking.booking_id, "| Station:", booking.station_name, "| Time:",
              booking.start_time, "-", booking.end_time, "| Status:", booking.status)


def make_booking(driver_id):
    areas = Scheduler.get_areas(stations)
    print("\nAvailable Areas:")
    for i in range(len(areas)):
        print(i + 1, "-", areas[i])
    area_choice = input("\nChoose your area: ")
    if not area_choice.isdigit() or int(area_choice) < 1 or int(area_choice) > len(areas):
        print("Invalid area choice.")
        return
    driver_area = areas[int(area_choice) - 1]

    print("\nAvailable Time Choices:")
    for i in range(len(all_slots)):
        print(i + 1, "-", all_slots[i], "-", calculate_end_time(all_slots[i]))
    slot_choice = input("\nChoose a time slot: ")
    if not slot_choice.isdigit() or int(slot_choice) < 1 or int(slot_choice) > len(all_slots):
        print("Invalid slot choice.")
        return
    start_time = all_slots[int(slot_choice) - 1]
    end_time = calculate_end_time(start_time)
    print("\nSelected Time:", start_time, "-", end_time)

    station_options = scheduler.find_suitable_stations(driver_area, stations, start_time, end_time, booking_service)
    if len(station_options) == 0:
        print("No suitable stations found for this area.")
        return
    best_station = Scheduler.find_best_station(station_options)
    scheduler.display_station_options(station_options, best_station)
    station_input = input("\nChoose a station number: ")
    if not station_input.isdigit() or int(station_input) < 1 or int(station_input) > len(station_options):
        print("Invalid station choice.")
        return
    selected_station = station_options[int(station_input) - 1]["station"]
    print("\nSelected Station:", selected_station.name)
    print("Location:", selected_station.location)
    print("Selected Time:", start_time, "-", end_time)
    booking_service.try_booking(driver_id, selected_station, start_time, end_time, waiting_queue)


def promote_waiting_requests(cancelled_booking, station):
    matching_requests = waiting_queue.get_matching_requests(cancelled_booking.station_id, cancelled_booking.start_time, cancelled_booking.end_time)
    if len(matching_requests) == 0:
        return
    request = matching_requests[0]
    conflict = booking_service.check_booking_overlap(station.station_id, request["start_time"], request["end_time"])
    if conflict:
        print("The time is still unavailable.")
        return
    booking_service.create_booking(request["driver_id"], station, request["start_time"], request["end_time"])
    waiting_queue.remove_request(request["request_id"])
    print("The released slot has been assigned to a waiting driver.")


def cancel_my_booking(driver_id):
    my_active_bookings = []

    for booking in booking_service.bookings:
        if booking.driver_id == driver_id and booking.status == "Confirmed":
            my_active_bookings.append(booking)
    if len(my_active_bookings) == 0:
        print("You have no active bookings to cancel.")
        return
    print("\nYour Active Bookings:")
    for booking in my_active_bookings:
        print("Booking ID:", booking.booking_id, "| Station:", booking.station_name,
              "| Time:", booking.start_time, "-", booking.end_time)
    booking_input = input("\nEnter Booking ID to cancel: ")
    if not booking_input.isdigit():
        print("Invalid Booking ID.")
        return
    booking_id = int(booking_input)
    selected_booking = None
    for booking in my_active_bookings:
        if booking.booking_id == booking_id:
            selected_booking = booking
            break
    if selected_booking is None:
        print("You can only cancel your own active bookings.")
        return
    booking = booking_service.cancel_booking(booking_id)
    if booking is None:
        print("Booking could not be cancelled.")
        return
    print("\nBooking cancelled successfully.")
    selected_station = None
    for station in stations:
        if station.station_id == booking.station_id:
            selected_station = station
            break
    if selected_station is None:
        print("Station not found.")
        return
    if booking.start_time not in selected_station.available_slots:
        selected_station.available_slots.append(booking.start_time)
        selected_station.available_slots.sort()
    print("The time slot has been released.")
    promote_waiting_requests(booking, selected_station)


def cancel_my_waiting_request(driver_id):
    my_requests = [request for request in waiting_queue.queue if request["driver_id"] == driver_id]
    if len(my_requests) == 0:
        print("You have no waiting requests.")
        return
    print("\nYour Waiting Requests:")
    for request in my_requests:
        station_name = "Unknown station"
        for station in stations:
            if station.station_id == request["station_id"]:
                station_name = station.name
                break
        print("Request ID:", request["request_id"], "| Station:", station_name,
              "| Time:", request["start_time"], "-", request["end_time"])
    request_input = input("\nEnter Request ID to cancel: ")
    if not request_input.isdigit():
        print("Invalid Request ID.")
        return
    request_id = int(request_input)
    request = waiting_queue.get_request(request_id)
    if request is None or request["driver_id"] != driver_id:
        print("Invalid request ID.")
        return
    waiting_queue.remove_request(request_id)
    print("Waiting request cancelled successfully.")


def admin_remove_waiting_request():
    display_waiting_list()
    if len(waiting_queue.queue) == 0:
        return
    request_input = input("\nEnter Request ID to remove: ")
    if not request_input.isdigit():
        print("Invalid Request ID.")
        return
    request = waiting_queue.remove_request(int(request_input))
    if request is None:
        print("Waiting request not found.")
    else:
        print("Request removed successfully.")


def user_dashboard(user):
    driver_id = get_driver_id(user)
    while True:
        print("\n================================")
        print("       ChargeSpot Dashboard")
        print("================================")
        print("Welcome:", user["name"])
        print("Driver ID:", driver_id)
        print("\n1 - Book a Charging Slot")
        print("2 - Cancel My Booking")
        print("3 - Cancel My Waiting Request")
        print("4 - Display My Bookings")
        if user.get("role") == "admin":
            print("5 - Admin: Display All Bookings and Waiting List")
            print("6 - Admin: Remove Waiting Request")
        print("0 - Logout")
        choice = input("\nChoose an option: ")
        if choice == "1":
            make_booking(driver_id)
        elif choice == "2":
            cancel_my_booking(driver_id)
        elif choice == "3":
            cancel_my_waiting_request(driver_id)
        elif choice == "4":
            display_my_bookings(driver_id)
        elif choice == "5" and user.get("role") == "admin":
            display_all_bookings()
            display_waiting_list()
        elif choice == "6" and user.get("role") == "admin":
            admin_remove_waiting_request()
        elif choice == "0":
            print("You have been logged out.")
            break
        else:
            print("Invalid choice. Try again.")


def main():
    print("\n================================")
    print("       Welcome to ChargeSpot")
    print("================================")
    while True:
        print("\nStart Menu")
        print("1 - Login")
        print("2 - Register")
        print("0 - Exit")
        choice = input("\nChoose an option: ")
        if choice == "1":
            user = login()
            if user is not None:
                user_dashboard(user)
        elif choice == "2":
            register_user()
        elif choice == "0":
            print("\nThank you for using ChargeSpot!")
            break
        else:
            print("Invalid choice. Try again.")


if __name__ == "__main__":
    main()
