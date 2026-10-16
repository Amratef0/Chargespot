"""Shared data contract for ChargeSpot (agreed by all 4 members in Week 1).

Every CSV column name, ID format and allowed value lives HERE so that no
member hard-codes a different spelling. If the team changes the schema,
change it in this file only.
"""
import re

DATETIME_FORMAT = "%Y-%m-%d %H:%M"          # every timestamp in every CSV
WEEKEND_DAYS = (4, 5)                        # Fri=4, Sat=5 (Egypt weekend)
WEEKDAY_NAMES = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")

BOOKING_STATUSES = ("Confirmed", "Waiting", "Completed", "Cancelled", "No-Show")
CONNECTORS = ("CCS2", "CHAdeMO", "Type 2")
CHARGER_TYPES = ("AC", "DC")
CHARGER_STATUSES = ("Available", "Occupied", "Maintenance")

MIN_DURATION_MIN = 15
MAX_DURATION_MIN = 240

ID_PATTERNS = {                  # the team's own ID formats (same patterns as utils/validators.py)
    "station": r"^\d{1,4}$",         # 12
    "charger": r"^(AC|DC)-\d{3}$",   # AC-101, DC-201
    "booking": r"^\d{1,9}$",         # 1042
    "session": r"^\d{1,9}$",
    "driver": r"^D\d{3,6}$",         # D101
}
ID_REGEX = {k: re.compile(v) for k, v in ID_PATTERNS.items()}

# Column order of each CSV file
STATION_COLS = ["station_id", "name", "city", "area", "address", "lat", "lon",
                "open_hour", "close_hour", "price_per_kwh"]
CHARGER_COLS = ["charger_id", "station_id", "charger_type", "connector",
                "power_kw", "status"]
VEHICLE_COLS = ["vehicle_model", "battery_kwh", "km_per_kwh", "connector"]
DRIVER_COLS = ["driver_id", "name", "vehicle_model", "connector"]
BOOKING_COLS = ["booking_id", "driver_id", "station_id", "charger_id",
                "connector", "created_at", "start_time", "end_time",
                "duration_min", "status", "queued", "wait_min"]
SESSION_COLS = ["session_id", "booking_id", "driver_id", "station_id",
                "charger_id", "planned_start", "actual_start", "actual_end",
                "duration_min", "delay_min", "energy_kwh", "cost_egp"]

# Columns the cleaner cannot work without
REQUIRED_BOOKING_COLS = ["booking_id", "station_id", "charger_id",
                        "connector", "start_time", "duration_min", "status"]
