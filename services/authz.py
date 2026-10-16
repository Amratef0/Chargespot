from __future__ import annotations

from models.exceptions import PermissionDeniedError

# page key -> user needs ANY of these permissions (empty tuple = any logged-in user)
PAGE_ACCESS: dict[str, tuple[str, ...]] = {
    "home": (),
    "stations": ("view_stations",),
    "bookings": ("book", "view_all_bookings"),
    "waiting": ("book", "manage_waiting"),
    "sessions": ("manage_sessions",),
    "driver": ("view_own", "view_any_driver"),
    "recommend": ("recommend",),
    "analytics": ("analytics",),
}


def authorize(user, *permissions: str):
    """Return `user` if they hold ANY of `permissions` (or none are required); otherwise raise PermissionDeniedError."""
    if user is None:
        raise PermissionDeniedError("Please log in first.")
    if permissions and not any(user.can(p) for p in permissions):
        raise PermissionDeniedError("You do not have permission to do this.")
    return user



def can_open(user, page_key: str) -> bool:
    if user is None or page_key not in PAGE_ACCESS:
        return False

    if page_key == "home" and user.role == "user":
        return False

    need = PAGE_ACCESS[page_key]
    return not need or any(user.can(p) for p in need)




def allowed_pages(user, page_keys) -> list[str]:
    return [
        k for k in page_keys
        if can_open(user, k)
        and not (k == "home" and user.role == "user")
    ]