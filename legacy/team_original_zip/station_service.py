# ============================================================================
# Imports
# ============================================================================
from stack import Stack
from station import Station
# ============================================================================
admin_stack = Stack()

def remove_charger_with_undo(station, charger_id):
    for charger in station.chargers:
        if charger["charger_id"] == charger_id:
            if charger.get("charger_status") == "Occupied":
                print(f"Cannot delete charger {charger_id} because it is currently Occupied!")
                return False
            undo_data = {
                "action": "remove_charger",
                "station": station,
                "charger_data": charger
            }
            admin_stack.push(undo_data)
            station.chargers.remove(charger)
            print(f"Charger {charger_id} removed successfully. (Recorded for Undo)")
            Station.save_to_json()
            return True
    print("Charger ID not found.")
    return False

def undo_last_admin_action():
    if admin_stack.is_empty():
        print("No actions to undo.")
        return False
    last_action = admin_stack.pop()
    if last_action["action"] == "remove_charger":
        station = last_action["station"]
        charger_data = last_action["charger_data"]
        station.chargers.append(charger_data)
        Station.save_to_json()
        print(f"Undo successful: Charger {charger_data['charger_id']} restored to station {station.name}.")
        return True
    return False