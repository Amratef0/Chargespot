"""Waiting list (Member 2's WaitingQueue, rebuilt on a real FIFO Queue).

Kept: class name, add_to_waiting_list, remove_request, get_request, get_matching_requests.
Changed: the list `self.queue` is now algorithms.queue.Queue (enqueue/dequeue/position);
requests carry connector, duration and full datetimes; queue POSITIONS are shown (PDF);
promotion handles any freed slot (it only matched identical start/end times before) and keeps FIFO order.
"""
from datetime import datetime

from algorithms.greedy_scheduler import pick_charger_greedy
from algorithms.interval_utils import intervals_overlap
from algorithms.queue import Queue
from models.exceptions import NotFoundError, SchedulingConflictError, ValidationError


class WaitingQueue:
    def __init__(self):
        self.queue = Queue()
        self.next_request_id = 1

    def add_to_waiting_list(self, driver_id, station_id, connector, start_time, duration_min, created_at=None):
        if not isinstance(duration_min, int) or duration_min <= 0:
            raise ValidationError("Waiting request needs a positive duration.")
        for r in self.queue:
            if r["driver_id"] == driver_id and r["station_id"] == station_id and r["start_time"] == start_time:
                raise ValidationError("You are already waiting for this station and time.")
        req = {"request_id": self.next_request_id, "driver_id": driver_id, "station_id": station_id,
               "connector": connector, "start_time": start_time, "duration_min": duration_min,
               "created_at": created_at or datetime.now()}
        self.next_request_id += 1
        req["position"] = self.queue.enqueue(req)
        return req

    def load_request(self, req):
        self.queue.enqueue(req)
        self.next_request_id = max(self.next_request_id, req["request_id"] + 1)

    def get_request(self, request_id):
        for r in self.queue:
            if r["request_id"] == request_id:
                return r
        return None

    def remove_request(self, request_id):
        return self.queue.remove_where(lambda r: r["request_id"] == request_id)

    def position(self, request_id):
        pos = self.queue.position_of(lambda r: r["request_id"] == request_id)
        if pos is None:
            raise NotFoundError(f"Waiting request {request_id} not found.")
        return pos

    def requests_for_driver(self, driver_id):
        return [(self.position(r["request_id"]), r) for r in self.queue if r["driver_id"] == driver_id]

    def get_matching_requests(self, station_id, start_time, end_time):
        """Waiting requests of a station whose wanted time overlaps [start_time, end_time), FIFO order."""
        out = []
        for r in self.queue:
            r_end = r["start_time"].timestamp() + r["duration_min"] * 60
            if r["station_id"] == station_id and intervals_overlap(
                    r["start_time"].timestamp(), r_end, start_time.timestamp(), end_time.timestamp()):
                out.append(r)
        return out

    def purge_expired(self, now=None):
        """Drop requests whose wanted start time has already passed."""
        now = now or datetime.now()
        gone = [r for r in self.queue if r["start_time"] < now]
        for r in gone:
            self.remove_request(r["request_id"])
        return gone

    def promote_eligible(self, station, booking_service, now=None):
        """A slot was freed: go through the queue in FIFO order and confirm every request that now fits.

        Returns [(request, booking)]. A request that still does not fit is skipped, not blocked-on.
        """
        now = now or datetime.now()
        promoted = []
        for r in self.queue.to_list():
            if r["station_id"] != station.station_id or r["start_time"] < now:
                continue
            start = r["start_time"]
            day, s = start.strftime("%Y-%m-%d"), start.hour * 60 + start.minute
            opt = pick_charger_greedy(station.usable_chargers(r["connector"]),
                                      lambda cid: booking_service.busy_intervals(cid, day),
                                      s, r["duration_min"], station.close_hour * 60, max_shift=0)
            if opt is None:
                continue
            charger = station.find_charger(opt.charger_id)
            try:
                b = booking_service.create_booking(
                    r["driver_id"], station, charger, start, r["duration_min"], now=now,
                    queued=1, wait_min=max(0, int((now - r["created_at"]).total_seconds() // 60)))
            except (SchedulingConflictError, ValidationError):
                continue
            self.remove_request(r["request_id"])
            promoted.append((r, b))
        return promoted
