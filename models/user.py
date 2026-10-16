"""User roles (PDF: a User base class with role subclasses). Polymorphism: each role answers
`permissions()` differently and the UI asks `user.can(action)` instead of checking role strings."""


class User:
    role = "user"
    label = "User"

    def __init__(self, name, email, phone="", age=0, gender="", governorate="", national_id="",
                 driver_id=None, vehicle_model=None, **_ignored):
        self.name, self.email, self.phone, self.age = name, email, phone, age
        self.gender, self.governorate, self.national_id = gender, governorate, national_id
        self.driver_id, self.vehicle_model = driver_id, vehicle_model

    def permissions(self):
        return set()

    def can(self, action):
        return action in self.permissions()


class Driver(User):
    role, label = "user", "Driver"

    def permissions(self):
        return {"book", "cancel_own", "view_own", "battery", "recommend", "view_stations"}


class StationOperator(User):
    role, label = "operator", "Station Operator"

    def permissions(self):
        return {"view_stations", "update_charger_status", "manage_sessions", "manage_waiting",
                "view_all_bookings"}


class Admin(StationOperator):
    role, label = "admin", "Administrator"

    def permissions(self):
        return super().permissions() | {"manage_stations", "undo", "analytics", "cancel_any", "recommend",
                                        "view_any_driver"}


ROLES = {"user": Driver, "operator": StationOperator, "admin": Admin}


def user_from_dict(d):
    cls = ROLES.get(d.get("role", "user"), Driver)
    return cls(**{k: v for k, v in d.items() if k not in ("role", "password", "password_hash")})
