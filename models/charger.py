"""Charger classes (Member 1). Inheritance: Charger -> ACCharger / DCCharger.
Added: validation (power, status, connector) and `charger_from_dict` factory."""
from models.exceptions import InvalidStatusError, ValidationError
from utils.validators import is_id

CHARGER_STATUSES = ("Available", "Occupied", "Maintenance")
AC_CONNECTORS = ("Type 2",)
DC_CONNECTORS = ("CCS2", "CHAdeMO")
ALL_CONNECTORS = AC_CONNECTORS + DC_CONNECTORS


class Charger:
    charger_type = "?"
    allowed_connectors = ALL_CONNECTORS

    def __init__(self, charger_id, charger_power_kw, charger_status="Available"):
        if not is_id("charger", charger_id):
            raise ValidationError(f"Invalid charger ID '{charger_id}'. Use AC-101 / DC-201 style IDs.")
        if isinstance(charger_power_kw, bool) or not isinstance(charger_power_kw, (int, float)) \
                or not 0 < charger_power_kw <= 500:
            raise ValidationError("Charger power must be a number between 0 and 500 kW.")
        if charger_status not in CHARGER_STATUSES:
            raise InvalidStatusError(f"Invalid status '{charger_status}'. Choose from: {list(CHARGER_STATUSES)}")
        self.charger_id = charger_id
        self.charger_power_kw = charger_power_kw
        self.charger_status = charger_status

    def get_info(self):
        return f"Charger ID: {self.charger_id}, Power: {self.charger_power_kw}kW, Status: {self.charger_status}"

    def casting_charge_to_dict(self):
        return {
            "charger_id": self.charger_id,
            "charger_power_kw": self.charger_power_kw,
            "charger_status": self.charger_status,
        }


class _Connected(Charger):
    def __init__(self, charger_id, charger_power_kw, connector_type, charger_status="Available"):
        super().__init__(charger_id, charger_power_kw, charger_status)
        if connector_type not in self.allowed_connectors:
            raise ValidationError(f"A {self.charger_type} charger cannot use connector '{connector_type}'. "
                                f"Allowed: {list(self.allowed_connectors)}")
        if not charger_id.startswith(self.charger_type + "-"):
            raise ValidationError(f"{self.charger_type} charger IDs must start with '{self.charger_type}-'.")
        self.connector_type = connector_type

    def get_info(self):
        return f"[{type(self).__name__}] {super().get_info()}, Connector Type: {self.connector_type}"

    def casting_charge_to_dict(self):
        d = super().casting_charge_to_dict()
        d["connector_type"] = self.connector_type
        d["type"] = self.charger_type
        return d


class ACCharger(_Connected):
    charger_type = "AC"
    allowed_connectors = AC_CONNECTORS

    def __init__(self, charger_id, charger_power_kw, connector_type="Type 2", charger_status="Available"):
        super().__init__(charger_id, charger_power_kw, connector_type, charger_status)


class DCCharger(_Connected):
    charger_type = "DC"
    allowed_connectors = DC_CONNECTORS

    def __init__(self, charger_id, charger_power_kw, connector_type="CCS2", charger_status="Available"):
        super().__init__(charger_id, charger_power_kw, connector_type, charger_status)


def charger_from_dict(d: dict) -> Charger:
    """Rebuild the right subclass from a stored dict (polymorphism after loading JSON)."""
    cls = {"AC": ACCharger, "DC": DCCharger}.get(d.get("type"))
    if cls is None:
        raise ValidationError(f"Unknown charger type '{d.get('type')}'.")
    return cls(d["charger_id"], d["charger_power_kw"], d.get("connector_type"), d.get("charger_status", "Available"))
