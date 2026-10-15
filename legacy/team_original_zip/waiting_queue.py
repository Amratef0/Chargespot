class WaitingQueue:
    def __init__(self):
        self.queue = []
        self.next_request_id = 1

    def add_to_waiting_list(self, driver_id, station_id, start_time, end_time):
        request = {"request_id": self.next_request_id, "driver_id": driver_id, "station_id": station_id, "start_time": start_time, "end_time": end_time}
        self.queue.append(request)
        self.next_request_id += 1
        return request

    def remove_request(self, request_id):
        for request in self.queue:
            if request["request_id"] == request_id:
                self.queue.remove(request)
                return request
        return None

    def get_request(self, request_id):
        for request in self.queue:
            if request["request_id"] == request_id:
                return request
        return None

    def get_matching_requests(self, station_id, start_time, end_time):
        matching_requests = []
        for request in self.queue:
            if request["station_id"] == station_id and request["start_time"] == start_time and request["end_time"] == end_time:
                matching_requests.append(request)
        return matching_requests
