"""Configuration commune aux pipelines Météo Maroc."""

MAX_RETRIES = 3

CITIES = {
    "Casablanca": (33.59, -7.62),
    "Rabat": (34.02, -6.84),
    "Marrakech": (31.63, -8.00),
    "Fès": (34.06, -4.98),
    "Tanger": (35.76, -5.83),
    "Agadir": (30.42, -9.60),
    "Oujda": (34.68, -1.91),
    "Meknès": (33.89, -5.55),
    "Tétouan": (35.57, -5.37),
    "Ouarzazate": (30.92, -6.91),
}

HOURLY_FIELDS = [
    "temperature_2m",
    "relative_humidity_2m",
    "precipitation",
    "wind_speed_10m",
]
