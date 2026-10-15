class ChargingSession:
    def __init__(
        self,
        session_id,
        booking_id,
        charger_id,
        user_id,
        planned_start=None,
        planned_duration_minutes=0.0,
    ):
        self.session_id = session_id
        self.booking_id = booking_id
        self.charger_id = charger_id
        self.user_id = user_id
        self.planned_start = planned_start
        self.planned_duration_minutes = float(planned_duration_minutes)
        self.start_time = None
        self.end_time = None
        self.duration_minutes = 0.0
        self.energy_delivered_kwh = 0.0
        self.status = "Planned"