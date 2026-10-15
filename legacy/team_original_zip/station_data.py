from station import Station

slots = [
    "00:00", "01:00", "02:00", "03:00", "04:00", "05:00",
    "06:00", "07:00", "08:00", "09:00", "10:00", "11:00",
    "12:00", "13:00", "14:00", "15:00", "16:00", "17:00",
    "18:00", "19:00", "20:00", "21:00", "22:00", "23:00"
]

stations = [
    Station(2, "ChargeSpot Smouha ", "Smouha", "Victor Emanuel", "Alexandria", "Available", slots.copy()),
    Station(3, "ChargeSpot Sidi Gaber", "Sidi Gaber", "Sidi Gaber Station", "Alexandria", "Available", slots.copy()),
    Station(4, "ChargeSpot Stanley", "Stanley", "Stanley Bridge", "Alexandria", "Available", slots.copy()),
    Station(5, "ChargeSpot San Stefano", "San Stefano", "San Stefano Mall", "Alexandria", "Available", slots.copy()),
    Station(6, "ChargeSpot Miami", "Miami", "Miami Beach", "Alexandria", "Available", slots.copy()),
    Station(7, "ChargeSpot Sporting", "Sporting", "Sporting Club", "Alexandria", "Available", slots.copy()),
    Station(8, "ChargeSpot Kafr Abdo", "Kafr Abdo", "Kafr Abdo Square", "Alexandria", "Available", slots.copy()),
    Station(9, "ChargeSpot Nasr City 1", "Nasr City", "Abbas El Akkad", "Cairo", "Available", slots.copy()),
    Station(10, "ChargeSpot Nasr City 2", "Nasr City", "Makram Ebeid", "Cairo", "Available", slots.copy()),
    Station(11, "ChargeSpot Heliopolis", "Heliopolis", "Korba", "Cairo", "Available", slots.copy()),
    Station(12, "ChargeSpot Maadi", "Maadi", "Maadi Grand Mall", "Cairo", "Available", slots.copy()),
    Station(13, "ChargeSpot New Cairo 1", "New Cairo", "Fifth Settlement", "Cairo", "Available", slots.copy()),
    Station(14, "ChargeSpot New Cairo 2", "New Cairo", "South 90th", "Cairo", "Available", slots.copy()),
    Station(15, "ChargeSpot Zamalek", "Zamalek", "Zamalek Square", "Cairo", "Available", slots.copy()),
    Station(16, "ChargeSpot Downtown", "Downtown", "Tahrir Square", "Cairo", "Available", slots.copy())
]

distances = {
    "Smouha": {"Smouha Club": 1.2, "Victor Emanuel": 2.0, "Sidi Gaber Station": 3.0, "Stanley Bridge": 5.0, "San Stefano Mall": 7.0, "Miami Beach": 9.0, "Sporting Club": 3.5, "Kafr Abdo Square": 2.5},
    "Sidi Gaber": {"Smouha Club": 3.0, "Victor Emanuel": 2.5, "Sidi Gaber Station": 1.0, "Stanley Bridge": 3.0, "San Stefano Mall": 5.0, "Miami Beach": 7.0, "Sporting Club": 2.5, "Kafr Abdo Square": 3.5},
    "Stanley": {"Smouha Club": 5.0, "Victor Emanuel": 4.5, "Sidi Gaber Station": 3.0, "Stanley Bridge": 1.0, "San Stefano Mall": 2.5, "Miami Beach": 4.5, "Sporting Club": 3.5, "Kafr Abdo Square": 4.5},
    "San Stefano": {"Smouha Club": 7.0, "Victor Emanuel": 6.5, "Sidi Gaber Station": 5.0, "Stanley Bridge": 2.5, "San Stefano Mall": 1.0, "Miami Beach": 2.5, "Sporting Club": 5.5, "Kafr Abdo Square": 5.5},
    "Miami": {"Smouha Club": 9.0, "Victor Emanuel": 8.5, "Sidi Gaber Station": 7.0, "Stanley Bridge": 4.5, "San Stefano Mall": 2.5, "Miami Beach": 1.0, "Sporting Club": 7.5, "Kafr Abdo Square": 7.5},
    "Sporting": {"Smouha Club": 3.5, "Victor Emanuel": 3.0, "Sidi Gaber Station": 2.5, "Stanley Bridge": 3.5, "San Stefano Mall": 5.5, "Miami Beach": 7.5, "Sporting Club": 1.0, "Kafr Abdo Square": 3.5},
    "Kafr Abdo": {"Smouha Club": 2.5, "Victor Emanuel": 2.5, "Sidi Gaber Station": 3.5, "Stanley Bridge": 4.5, "San Stefano Mall": 5.5, "Miami Beach": 7.5, "Sporting Club": 3.5, "Kafr Abdo Square": 1.0},
    "Nasr City": {"Abbas El Akkad": 1.2, "Makram Ebeid": 2.0, "Korba": 7.0, "Maadi Grand Mall": 15.0, "Fifth Settlement": 12.0, "South 90th": 13.0, "Zamalek Square": 12.0, "Tahrir Square": 10.0},
    "Heliopolis": {"Abbas El Akkad": 6.5, "Makram Ebeid": 7.0, "Korba": 1.0, "Maadi Grand Mall": 18.0, "Fifth Settlement": 14.0, "South 90th": 15.0, "Zamalek Square": 11.0, "Tahrir Square": 9.0},
    "Maadi": {"Abbas El Akkad": 15.0, "Makram Ebeid": 16.0, "Korba": 18.0, "Maadi Grand Mall": 1.0, "Fifth Settlement": 13.0, "South 90th": 14.0, "Zamalek Square": 12.0, "Tahrir Square": 10.0},
    "New Cairo": {"Abbas El Akkad": 12.0, "Makram Ebeid": 13.0, "Korba": 14.0, "Maadi Grand Mall": 13.0, "Fifth Settlement": 1.5, "South 90th": 2.0, "Zamalek Square": 18.0, "Tahrir Square": 15.0},
    "Zamalek": {"Abbas El Akkad": 12.0, "Makram Ebeid": 13.0, "Korba": 11.0, "Maadi Grand Mall": 12.0, "Fifth Settlement": 18.0, "South 90th": 19.0, "Zamalek Square": 1.0, "Tahrir Square": 4.0},
    "Downtown": {"Abbas El Akkad": 10.0, "Makram Ebeid": 11.0, "Korba": 9.0, "Maadi Grand Mall": 10.0, "Fifth Settlement": 15.0, "South 90th": 16.0, "Zamalek Square": 4.0, "Tahrir Square": 1.0}
}
