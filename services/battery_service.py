from models.exceptions import InvalidBatteryValueError


class BatteryService:
    def __init__(self, capacity_kwh, km_per_kwh, efficiency=0.9):
        for name, value in (
            ("Battery capacity", capacity_kwh),
            ("Range efficiency", km_per_kwh),
            ("Charging efficiency", efficiency),
        ):
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                raise InvalidBatteryValueError(f"{name} must be a number.")

        if capacity_kwh <= 0:
            raise InvalidBatteryValueError(
                "Battery capacity must be greater than 0."
            )
        if km_per_kwh <= 0:
            raise InvalidBatteryValueError(
                "Range efficiency must be greater than 0."
            )
        if not 0 < efficiency <= 1:
            raise InvalidBatteryValueError(
                "Charging efficiency must be greater than 0 and at most 1."
            )

        self.capacity_kwh = float(capacity_kwh)
        self.km_per_kwh = float(km_per_kwh)
        self.efficiency = float(efficiency)

    def calculate_estimates(self, current_pct, target_pct, charger_power_kw):
        for name, value in (
            ("Current battery percentage", current_pct),
            ("Target battery percentage", target_pct),
            ("Charger power", charger_power_kw),
        ):
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                raise InvalidBatteryValueError(f"{name} must be a number.")

        if not 0 <= current_pct <= 100:
            raise InvalidBatteryValueError(
                "Current battery percentage must be between 0 and 100."
            )

        if not current_pct < target_pct <= 100:
            raise InvalidBatteryValueError(
                "Target percentage must be greater than current and up to 100."
            )

        if charger_power_kw <= 0:
            raise InvalidBatteryValueError(
                "Charger power must be greater than 0."
            )

        energy_needed = self.capacity_kwh * (target_pct - current_pct) / 100
        estimated_time_hours = energy_needed / (
            charger_power_kw * self.efficiency
        )
        energy_remaining = self.capacity_kwh * current_pct / 100
        estimated_range_km = energy_remaining * self.km_per_kwh

        return {
            "energy_needed_kwh": round(energy_needed, 2),
            "estimated_time_hours": round(estimated_time_hours, 2),
            "estimated_range_km": round(estimated_range_km, 2),
            "low_battery_warning": current_pct < 20,
        }