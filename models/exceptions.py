


class ChargeSpotError(Exception):
    """Base class of every error raised on purpose by ChargeSpot."""


class InvalidSessionStateError(ChargeSpotError):
    pass


class InvalidBatteryValueError(ChargeSpotError):
    pass


class ValidationError(ChargeSpotError):
    """Input failed validation (format, range, missing value)."""


class DuplicateIDError(ChargeSpotError):
    pass


class NotFoundError(ChargeSpotError):
    pass


class SchedulingConflictError(ChargeSpotError):
    """The requested slot overlaps an existing booking on that charger."""


class ChargerInUseError(ChargeSpotError):
    """Charger/station cannot be removed or changed because it is busy or booked."""


class InvalidStatusError(ChargeSpotError):
    pass


class AuthError(ChargeSpotError):
    pass


class PermissionDeniedError(AuthError):
    """Nobody is logged in, or the logged-in user's role does not allow this action."""


class EmailNotVerifiedError(AuthError):
    """The password was correct but the e-mail address has not been verified yet."""


class TokenError(AuthError):
    """A verification / reset token is unknown, expired or already used."""


class UnsortedDataError(ChargeSpotError, ValueError):
    """Binary search was asked to work on data that is not sorted."""
