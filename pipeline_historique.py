import calendar
import logging
import os
import time
from datetime import UTC, datetime

import psycopg
import requests
from dotenv import load_dotenv

# ============================================================
# 1. CONFIGURATION
# ============================================================

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger(__name__)

API_URL = "https://archive-api.open-meteo.com/v1/archive"

START_YEAR = 2016
END_YEAR = 2025

MAX_RETRIES = 3
REQUEST_TIMEOUT = 60

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


# ============================================================
# 2. GENERATION DES PERIODES MENSUELLES
# ============================================================


def generate_months(start_year, end_year):
    for year in range(start_year, end_year + 1):
        for month in range(1, 13):
            last_day = calendar.monthrange(year, month)[1]

            start_date = f"{year}-{month:02d}-01"
            end_date = f"{year}-{month:02d}-{last_day:02d}"

            yield start_date, end_date


# ============================================================
# 3. EXTRACTION
# ============================================================


def extract(session, city, latitude, longitude, start_date, end_date):

    params = {
        "latitude": latitude,
        "longitude": longitude,
        "start_date": start_date,
        "end_date": end_date,
        "hourly": ",".join(HOURLY_FIELDS),
        "timezone": "GMT",
        "timeformat": "unixtime",
    }

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logger.info(
                "EXTRACT | %s | %s -> %s | tentative %s/%s",
                city,
                start_date,
                end_date,
                attempt,
                MAX_RETRIES,
            )

            response = session.get(
                API_URL,
                params=params,
                timeout=REQUEST_TIMEOUT,
            )

            response.raise_for_status()

            return response.json()

        except (requests.RequestException, ValueError) as exc:
            status_code = (
                exc.response.status_code
                if isinstance(exc, requests.HTTPError) and exc.response is not None
                else None
            )

            retryable = status_code is None or status_code == 429 or status_code >= 500

            if not retryable or attempt == MAX_RETRIES:
                raise

            delay = 2**attempt

            logger.warning(
                "RETRY | %s | erreur : %s | attente %ss",
                city,
                exc,
                delay,
            )

            time.sleep(delay)


# ============================================================
# 4. TRANSFORMATION
# ============================================================


def transform(city, data):

    hourly = data["hourly"]

    times = hourly["time"]
    temperatures = hourly["temperature_2m"]
    humidities = hourly["relative_humidity_2m"]
    precipitations = hourly["precipitation"]
    wind_speeds = hourly["wind_speed_10m"]

    expected_length = len(times)

    if not all(
        len(values) == expected_length
        for values in (
            temperatures,
            humidities,
            precipitations,
            wind_speeds,
        )
    ):
        raise ValueError(f"Tableaux météo de tailles différentes pour {city}")

    rows = []

    for i in range(expected_length):
        observed_at = datetime.fromtimestamp(
            times[i],
            tz=UTC,
        )

        row = (
            city,
            observed_at,
            temperatures[i],
            humidities[i],
            precipitations[i],
            wind_speeds[i],
        )

        rows.append(row)

    return rows


# ============================================================
# 5. CHARGEMENT POSTGRESQL
# ============================================================

UPSERT_SQL = """
INSERT INTO weather_history (
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

    with (
        psycopg.connect(
            host=os.getenv("POSTGRES_HOST", "127.0.0.1"),
            port=int(os.getenv("POSTGRES_PORT", "5433")),
            dbname=os.environ["POSTGRES_DB"],
            user=os.environ["POSTGRES_USER"],
            password=os.environ["POSTGRES_PASSWORD"],
            connect_timeout=10,
        ) as conn,
        conn.cursor() as cur,
    ):
        cur.executemany(UPSERT_SQL, rows)

    return len(rows)


# ============================================================
# 6. ORCHESTRATION DU PIPELINE
# ============================================================


def main():

    total_rows = 0
    successful_batches = 0
    failed_batches = 0

    months = list(generate_months(START_YEAR, END_YEAR))

    logger.info(
        "START | %s villes | %s mois | %s lots prévus",
        len(CITIES),
        len(months),
        len(CITIES) * len(months),
    )

    with requests.Session() as session:
        for city, (latitude, longitude) in CITIES.items():
            logger.info("CITY START | %s", city)

            for start_date, end_date in months:
                try:
                    data = extract(
                        session,
                        city,
                        latitude,
                        longitude,
                        start_date,
                        end_date,
                    )

                    rows = transform(city, data)

                    loaded = load(rows)

                    total_rows += loaded
                    successful_batches += 1

                    logger.info(
                        "SUCCESS | %s | %s -> %s | %s lignes",
                        city,
                        start_date,
                        end_date,
                        loaded,
                    )

                except Exception:
                    failed_batches += 1

                    logger.exception(
                        "FAILED | %s | %s -> %s",
                        city,
                        start_date,
                        end_date,
                    )

                    continue

            logger.info("CITY END | %s", city)

    logger.info("=" * 60)
    logger.info("PIPELINE TERMINE")
    logger.info("Lots réussis : %s", successful_batches)
    logger.info("Lots échoués : %s", failed_batches)
    logger.info("Lignes traitées : %s", total_rows)
    logger.info("=" * 60)

    if failed_batches:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
