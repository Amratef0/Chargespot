from datetime import datetime

from algorithms.sorting import merge_sort
from models.charging_session import ChargingSession
from models.exceptions import InvalidSessionStateError


class SessionService:
    def __init__(self):
        self.sessions = []

    def create_session(
        self,
        session_id,
        booking_id,
        charger_id,
        user_id,
        planned_start=None,
        planned_duration_minutes=0.0,
    ):
        if self.get_session(session_id) is not None:
            raise ValueError(f"Session ID already exists: {session_id}")

        session = ChargingSession(
            session_id=session_id,
            booking_id=booking_id,
            charger_id=charger_id,
            user_id=user_id,
            planned_start=planned_start,
            planned_duration_minutes=planned_duration_minutes,
        )
        self.sessions.append(session)
        return session

    def start_session(
        self,
        session_id,
        booking_status="Confirmed",
        charger_status="Available",
    ):
        session = self.get_session(session_id)
        if session is None:
            raise ValueError("Session not found.")

        if session.status != "Planned":
            raise InvalidSessionStateError(
                "Cannot start session. Status must be Planned."
            )

        if booking_status != "Confirmed":
            raise InvalidSessionStateError(
                f"Cannot start session for a {booking_status} booking."
            )

        if charger_status != "Available":
            raise InvalidSessionStateError(
                f"Cannot start session. Charger is currently {charger_status}."
            )

        for existing in self.sessions:
            if (
                existing.charger_id == session.charger_id
                and existing.status == "Active"
            ):
                raise InvalidSessionStateError(
                    "Cannot start session. Charger is already occupied by an active session."
                )

        session.start_time = datetime.now()
        session.status = "Active"
        return session

    def complete_session(self, session_id, simulated_energy_kwh):
        session = self.get_session(session_id)
        if session is None:
            raise ValueError("Session not found.")

        if session.status != "Active":
            raise InvalidSessionStateError(
                "Cannot complete session. Status must be Active."
            )

        if not isinstance(simulated_energy_kwh, (int, float)) or isinstance(
            simulated_energy_kwh, bool
        ):
            raise ValueError("Energy delivered must be a valid number.")

        if simulated_energy_kwh <= 0:
            raise ValueError("Energy delivered must be greater than 0.")

        end_time = datetime.now()
        duration_minutes = (
            end_time - session.start_time
        ).total_seconds() / 60.0

        session.end_time = end_time
        session.duration_minutes = round(duration_minutes, 2)
        session.energy_delivered_kwh = round(float(simulated_energy_kwh), 2)
        session.status = "Completed"
        return session

    def get_session(self, session_id):
        for session in self.sessions:
            if session.session_id == session_id:
                return session
        return None

    def filter_sessions(self, user_id=None, charger_id=None, status=None):
        results = []
        for session in self.sessions:
            if user_id is not None and session.user_id != user_id:
                continue
            if charger_id is not None and session.charger_id != charger_id:
                continue
            if status is not None and session.status != status:
                continue
            results.append(session)
        return results

    def sort_session_history(
        self, key_str="start_time", reverse=False, sessions=None
    ):
        target_sessions = self.sessions if sessions is None else sessions

        key_map = {
            "start_time": lambda session: (
                session.start_time.timestamp() if session.start_time else 0
            ),
            "duration": lambda session: session.duration_minutes,
            "energy": lambda session: session.energy_delivered_kwh,
        }

        if key_str not in key_map:
            raise ValueError(
                "Invalid sort key. Choose 'start_time', 'duration', or 'energy'."
            )

        return merge_sort(
            target_sessions,
            key=key_map[key_str],
            reverse=reverse,
        )