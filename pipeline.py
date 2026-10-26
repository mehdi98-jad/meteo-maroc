
import logging
import os
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import psycopg
import requests
from dotenv import load_dotenv


# --------------------------------------------------
# 1. CONFIGURATION
# --------------------------------------------------

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger(__name__)

API_URL = "https://api.open-meteo.com/v1/forecast"
TIMEZONE = ZoneInfo("Africa/Casablanca")

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


# --------------------------------------------------
# 2. EXTRACTION
# --------------------------------------------------

def extract(session, city, latitude, longitude):
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "hourly": ",".join(HOURLY_FIELDS),
        "timezone": "Africa/Casablanca",
        "forecast_days": 1,
    }

    max_attempts = 3

    for attempt in range(1, max_attempts + 1):
        try:
            response = session.get(
                API_URL,
                params=params,
                timeout=20,
            )

            # Les erreurs HTTP 4xx/5xx deviennent
            # des exceptions Python.
            response.raise_for_status()

            return response.json()

        except (requests.RequestException, ValueError) as error:
            # 429 = limite de requêtes
            # 5xx = erreur du serveur
            # Erreurs réseau = pas de réponse HTTP
            status = (
                error.response.status_code
                if isinstance(error, requests.HTTPError)
                and error.response is not None
                else None
            )

            retryable = (
                not isinstance(error, requests.HTTPError)
                or status == 429
                or (status is not None and status >= 500)
            )

            if not retryable or attempt == max_attempts:
                raise

            wait_seconds = 2 ** attempt

            logger.warning(
                "%s | tentative %s/%s échouée : %s | "
                "nouvel essai dans %ss",
                city,
                attempt,
                max_attempts,
                error,
                wait_seconds,
            )

            time.sleep(wait_seconds)


# --------------------------------------------------
# 3. TRANSFORMATION
# --------------------------------------------------

def transform(city, payload):
    hourly = payload["hourly"]
    times = hourly["time"]

    # Toutes les séries doivent correspondre
    # aux mêmes positions horaires.
    for field in HOURLY_FIELDS:
        if len(hourly[field]) != len(times):
            raise ValueError(
                f"{city}: longueur incohérente pour {field}"
            )

    rows = []

    for index, time_string in enumerate(times):
        # Open-Meteo retourne des heures locales.
        local_datetime = datetime.fromisoformat(
            time_string
        ).replace(tzinfo=TIMEZONE)

        row = (
            city,
            local_datetime,
            hourly["temperature_2m"][index],
            hourly["relative_humidity_2m"][index],
            hourly["precipitation"][index],
            hourly["wind_speed_10m"][index],
        )

        rows.append(row)

    return rows


# --------------------------------------------------
# 4. CHARGEMENT
# --------------------------------------------------

UPSERT_SQL = """
INSERT INTO weather_observations (
    city,
    observed_at,
    temperature_c,
    humidity_pct,
    precipitation_mm,
    wind_speed_kmh
)
VALUES (%s, %s, %s, %s, %s, %s)
ON CONFLICT (city, observed_at)
DO UPDATE SET
    temperature_c = EXCLUDED.temperature_c,
    humidity_pct = EXCLUDED.humidity_pct,
    precipitation_mm = EXCLUDED.precipitation_mm,
    wind_speed_kmh = EXCLUDED.wind_speed_kmh;
"""


def load(rows):
    if not rows:
        return 0

    with psycopg.connect(
        host=os.environ["POSTGRES_HOST"],
        port=int(os.environ["POSTGRES_PORT"]),
        dbname=os.environ["POSTGRES_DB"],
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
        connect_timeout=10,
    ) as connection:
        with connection.cursor() as cursor:
            cursor.executemany(UPSERT_SQL, rows)

    # Le bloc connection valide la transaction
    # si aucune exception n'a été levée.
    return len(rows)


# --------------------------------------------------
# 5. ORCHESTRATION
# --------------------------------------------------

def main():
    success_count = 0
    failure_count = 0
    total_rows = 0

    logger.info("Démarrage du pipeline météo : %s villes", len(CITIES))

    with requests.Session() as session:
        for city, (latitude, longitude) in CITIES.items():
            logger.info("%s | début du traitement", city)

            try:
                payload = extract(
                    session, city, latitude, longitude
                )

                rows = transform(city, payload)

                loaded = load(rows)

                success_count += 1
                total_rows += loaded

                logger.info(
                    "%s | succès | %s lignes chargées",
                    city,
                    loaded,
                )

            except Exception as error:
                failure_count += 1

                logger.error(
                    "%s | échec | %s: %s",
                    city,
                    type(error).__name__,
                    error,
                )

                # On continue avec la ville suivante.
                continue

    logger.info(
        "BILAN | succès=%s | échecs=%s | lignes=%s",
        success_count,
        failure_count,
        total_rows,
    )

    if failure_count:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
