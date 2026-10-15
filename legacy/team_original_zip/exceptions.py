class ChargeSpotError(Exception):
    pass

class InvalidSessionStateError(ChargeSpotError):
    pass

class InvalidBatteryValueError(ChargeSpotError):
    pass
