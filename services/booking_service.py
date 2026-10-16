from datetime import datetime, timedelta

from algorithms.hash_table import HashTable
from algorithms.interval_utils import intervals_overlap, time_to_minutes
from algorithms.searching import insertion_point
from algorithms.sorting import merge_sort
from models.booking import Booking
from models.exceptions import (NotFoundError, SchedulingConflictError, ValidationError)

MIN_DURATION, MAX_DURATION, STEP = 15, 240, 15
BLOCKING = ("Confirmed", "Completed", "No-Show")      # statuses that occupy the charger


def _day(dt):
    return dt.strftime("%Y-%m-%d")


def _minute(dt):
    return dt.hour * 60 + dt.minute


class BookingService:
    def __init__(self):
        self.bookings = []
        self._by_id = HashTable(1024)
        self._busy = {}                   # (charger_id, "YYYY-MM-DD") -> [(start_min, end_min, booking_id)] sorted
        self._next_id = 1
        self.search_comparisons = 0       # binary-search work done (algorithm evidence)

    # ------------------------------------------------------------ helpers (names kept from Member 2)
    @staticmethod
    def time_to_minutes(time):
        return time_to_minutes(time)

    @staticmethod
    def is_overlap(start1, end1, start2, end2):
        return intervals_overlap(start1, end1, start2, end2)

    def busy_intervals(self, charger_id, day):
        """Sorted busy intervals [(start_min, end_min, booking_id)] of a charger on a day ('YYYY-MM-DD')."""
        return self._busy.get((charger_id, day), [])

    def check_booking_overlap(self, charger_id, start, end):
        """True if [start, end) overlaps an existing booking on that charger. start/end are datetimes."""
        lst = self.busy_intervals(charger_id, _day(start))
        s, e = _minute(start), _minute(end) if end.date() == start.date() else 1440
        pos, comps = insertion_point(lst, s, key=lambda iv: iv[0])     # binary search on sorted starts
        self.search_comparisons += comps
        before = lst[pos - 1] if pos > 0 else None                     # disjoint + sorted => only neighbours matter
        after = lst[pos] if pos < len(lst) else None
        return any(n is not None and intervals_overlap(s, e, n[0], n[1]) for n in (before, after))

    def _index(self, b):
        lst = self._busy.setdefault((b.charger_id, _day(b.start_time)), [])
        s, e = _minute(b.start_time), _minute(b.end_time)
        pos, _ = insertion_point(lst, s, key=lambda iv: iv[0])
        lst.insert(pos, (s, e, b.booking_id))

    def _unindex(self, b):
        lst = self._busy.get((b.charger_id, _day(b.start_time)), [])
        for i, iv in enumerate(lst):
            if iv[2] == b.booking_id:
                lst.pop(i)
                return

    # ------------------------------------------------------------ create / load
    def validate_request(self, station, charger, start, duration_min, now=None, allow_past=False):
        if isinstance(duration_min, bool) or not isinstance(duration_min, int) \
                or not MIN_DURATION <= duration_min <= MAX_DURATION or duration_min % STEP:
            raise ValidationError(f"Duration must be a multiple of {STEP} minutes between {MIN_DURATION} and {MAX_DURATION}.")
        if start.minute % STEP or start.second:
            raise ValidationError(f"Start time must be on a {STEP}-minute step (e.g. 10:00, 10:15).")
        if charger.get("charger_status") == "Maintenance":
            raise ValidationError(f"Charger {charger['charger_id']} is under maintenance.")
        s, e = _minute(start), _minute(start) + duration_min
        if s < station.open_hour * 60 or e > station.close_hour * 60:
            raise ValidationError(f"{station.name} is open {station.open_hour:02d}:00-{station.close_hour:02d}:00; "
                                "the session must finish before closing time.")
        if not allow_past and start < (now or datetime.now()):
            raise ValidationError("You cannot book a time in the past.")

    def create_booking(self, driver_id, station, charger, start, duration_min, now=None, allow_past=False,
                    queued=0, wait_min=0, created_at=None):
        self.validate_request(station, charger, start, duration_min, now, allow_past)
        end = start + timedelta(minutes=duration_min)
        if self.check_booking_overlap(charger["charger_id"], start, end):
            raise SchedulingConflictError(
                f"{charger['charger_id']} is already booked between {start:%H:%M} and {end:%H:%M} on {start:%Y-%m-%d}.")
        b = Booking(self._next_id, driver_id, station.station_id, station.name, station.area, start, end,
                    "Confirmed", charger["charger_id"], charger.get("connector_type"),
                    created_at or now or datetime.now(), queued, wait_min)
        self._register(b)
        return b

    def load_booking(self, b):
        """Add a booking read from storage (no validation: it was validated when it was created)."""
        self._register(b)
        return b

    def _register(self, b):
        self.bookings.append(b)
        self._by_id.put(b.booking_id, b)
        self._next_id = max(self._next_id, b.booking_id + 1)
        if b.status in BLOCKING and b.charger_id:
            self._index(b)

    # ------------------------------------------------------------ lookup
    def get_booking(self, booking_id):
        try:
            b = self._by_id.get(int(booking_id))
        except (TypeError, ValueError):
            b = None
        if b is None:
            raise NotFoundError(f"Booking {booking_id} not found.")
        return b

    def list_bookings(self, driver_id=None, status=None, station_id=None):
        return [b for b in self.bookings if (driver_id is None or b.driver_id == driver_id)
                and (status is None or b.status == status) and (station_id is None or b.station_id == station_id)]

    def sorted_by_start(self, bookings=None, reverse=False):
        """Bookings ordered by start time with the team's Merge Sort -> (sorted_list, comparisons)."""
        return merge_sort(self.bookings if bookings is None else bookings,
                        key=lambda b: b.start_time, reverse=reverse)

    # ------------------------------------------------------------ status changes
    def cancel_booking(self, booking_id, driver_id=None):
        b = self.get_booking(booking_id)
        if driver_id is not None and b.driver_id != driver_id:
            raise ValidationError("You can only cancel your own bookings.")
        if b.status != "Confirmed":
            raise ValidationError(f"Only Confirmed bookings can be cancelled (this one is {b.status}).")
        b.status = "Cancelled"
        self._unindex(b)                                   # frees the slot
        return b

    def mark_completed(self, booking_id):
        b = self.get_booking(booking_id)
        if b.status != "Confirmed":
            raise ValidationError(f"Booking {booking_id} is {b.status}, not Confirmed.")
        b.status = "Completed"
        return b

    def mark_no_show(self, booking_id):
        b = self.get_booking(booking_id)
        if b.status != "Confirmed":
            raise ValidationError(f"Booking {booking_id} is {b.status}, not Confirmed.")
        b.status = "No-Show"
        return b

    def has_active_bookings(self, charger_id, now=None):
        now = now or datetime.now()
        return any(b.charger_id == charger_id and b.status == "Confirmed" and b.end_time > now for b in self.bookings)

    # ------------------------------------------------------------ 2-D structure: charger x hour grid
    def availability_grid(self, station, day):
        """2-D list: one row per charger, 24 columns (hours) -> 'Free' | 'Booked' | 'Maintenance'."""
        grid = []
        for c in station.chargers:
            row = []
            for h in range(24):
                if c.get("charger_status") == "Maintenance":
                    row.append("Maintenance")
                    continue
                busy = any(intervals_overlap(h * 60, h * 60 + 60, s, e)
                        for s, e, _ in self.busy_intervals(c["charger_id"], day))
                row.append("Booked" if busy else "Free")
            grid.append(row)
        return grid
