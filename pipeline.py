
import logging
import os
import time

from datetime import datetime, timezone

import psycopg
import requests

from dotenv import load_dotenv

from storage import (
    get_s3_client,
    ensure_bucket,
    save_raw_json,
)


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

API_URL = "https://api.open-meteo.com/v1/forecast"

MAX_RETRIES = 3
REQUEST_TIMEOUT = 30

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
# 2. EXTRACTION - OPEN-METEO API
# ============================================================

def extract(session, city, latitude, longitude):

    params = {
        "latitude": latitude,
        "longitude": longitude,
        "hourly": ",".join(HOURLY_FIELDS),
        "timezone": "GMT",
        "timeformat": "unixtime",
        "forecast_days": 1,
    }

    for attempt in range(1, MAX_RETRIES + 1):

        try:
            logger.info(
                "EXTRACT | %s | tentative %s/%s",
                city,
                attempt,
                MAX_RETRIES,
            )

            response = session.get(
                API_URL,
                params=params,
                timeout=REQUEST_TIMEOUT,
            )

            response.raise_for_status()

            data = response.json()

            return data

        except (requests.RequestException, ValueError) as exc:

            status_code = (
                exc.response.status_code
                if isinstance(exc, requests.HTTPError)
                and exc.response is not None
                else None
            )

            retryable = (
                status_code is None
                or status_code == 429
                or status_code >= 500
            )

            if not retryable or attempt == MAX_RETRIES:
                raise

            delay = 2 ** attempt

            logger.warning(
                "RETRY | %s | %s | attente %ss",
                city,
                exc,
                delay,
            )

            time.sleep(delay)


# ============================================================
# 3. RAW DATA - SEAWEEDFS DATA LAKE
# ============================================================

def save_to_data_lake(s3_client, city, data, run_date):

    key = save_raw_json(
        s3_client,
        city,
        data,
        run_date,
    )

    logger.info(
        "RAW SAVED | %s | bucket=meteo-raw | key=%s",
        city,
        key,
    )

    return key


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
        raise ValueError(
            f"Tailles des tableaux incohérentes pour {city}"
        )

    rows = []

    for i in range(expected_length):

        observed_at = datetime.fromtimestamp(
            times[i],
            tz=timezone.utc,
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

    logger.info(
        "TRANSFORM | %s | %s observations",
        city,
        len(rows),
    )

    return rows


# ============================================================
# 5. POSTGRESQL UPSERT
# ============================================================

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
        host=os.getenv("POSTGRES_HOST", "127.0.0.1"),
        port=int(os.getenv("POSTGRES_PORT", "5433")),
        dbname=os.environ["POSTGRES_DB"],
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
        connect_timeout=10,
    ) as conn:

        with conn.cursor() as cur:
            cur.executemany(
                UPSERT_SQL,
                rows,
            )

    return len(rows)


# ============================================================
# 6. PIPELINE ORCHESTRATION
# ============================================================

def main():

    successful_cities = 0
    failed_cities = 0
    total_rows = 0

    run_date = datetime.now(timezone.utc).date().isoformat()

    logger.info("=" * 60)
    logger.info("START WEATHER ETL PIPELINE")
    logger.info("RUN DATE UTC | %s", run_date)
    logger.info("CITIES | %s", len(CITIES))
    logger.info("=" * 60)

    # Initialize SeaweedFS before processing cities.
    # If the data lake is unavailable, do not load PostgreSQL.

    try:
        s3_client = get_s3_client()
        ensure_bucket(s3_client)

        logger.info(
            "DATA LAKE READY | bucket=meteo-raw"
        )

    except Exception:
        logger.exception(
            "DATA LAKE UNAVAILABLE | pipeline stopped"
        )
        raise SystemExit(1)

    # Reuse the HTTP session for all cities.

    with requests.Session() as session:

        for city, (latitude, longitude) in CITIES.items():

            logger.info("-" * 60)
            logger.info("CITY START | %s", city)

            try:

                # STEP 1: Extract raw JSON from Open-Meteo.

                data = extract(
                    session,
                    city,
                    latitude,
                    longitude,
                )

                # STEP 2: Save JSON to SeaweedFS FIRST.
                # If this fails, PostgreSQL is not loaded.

                save_to_data_lake(
                    s3_client,
                    city,
                    data,
                    run_date,
                )

                # STEP 3: Transform JSON into database rows.

                rows = transform(
                    city,
                    data,
                )

                # STEP 4: Load into PostgreSQL.

                loaded = load(rows)

                successful_cities += 1
                total_rows += loaded

                logger.info(
                    "SUCCESS | %s | %s rows processed",
                    city,
                    loaded,
                )

            except Exception:

                failed_cities += 1

                logger.exception(
                    "FAILED | %s",
                    city,
                )

                # Continue with the next city.
                continue

    logger.info("=" * 60)
    logger.info("PIPELINE FINISHED")
    logger.info("Successful cities : %s", successful_cities)
    logger.info("Failed cities     : %s", failed_cities)
    logger.info("Rows processed    : %s", total_rows)
    logger.info("=" * 60)

    if failed_cities:
        raise SystemExit(1)


# ============================================================
# 7. ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()
