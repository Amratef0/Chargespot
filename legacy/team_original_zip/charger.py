class Charger:
    def __init__(self, charger_id, charger_power_kw, charger_status="Available"):
        self.charger_id = charger_id
        self.charger_power_kw = charger_power_kw
        self.charger_status = charger_status

    def get_info(self):
        return f"Charger ID: {self.charger_id}, Power: {self.charger_power_kw}kW, Status: {self.charger_status}"

    def casting_charge_to_dict(self):
        return {
            "charger_id": self.charger_id,
            "charger_power_kw": self.charger_power_kw,
            "charger_status": self.charger_status
        }

class ACCharger(Charger):
    def __init__(self, charger_id, charger_power_kw, connector_type="Type 2", charger_status="Available"):
        super().__init__(charger_id, charger_power_kw, charger_status)
        self.connector_type = connector_type

    def get_info(self):
        return f"[ACCharger] {super().get_info()}, Connector Type: {self.connector_type}"

    def casting_charge_to_dict(self):
        ACdict = super().casting_charge_to_dict()
        ACdict['connector_type'] = self.connector_type
        ACdict['type'] = "AC"
        return ACdict

class DCCharger(Charger):
    def __init__(self, charger_id, charger_power_kw, connector_type="CCS2", charger_status="Available"):
        super().__init__(charger_id, charger_power_kw, charger_status)
        self.connector_type = connector_type

    def get_info(self):
        return f"[DCCharger] {super().get_info()}, Connector Type: {self.connector_type}"

    def casting_charge_to_dict(self):
        DCdict = super().casting_charge_to_dict()
        DCdict['connector_type'] = self.connector_type
        DCdict['type'] = "DC"
        return DCdict