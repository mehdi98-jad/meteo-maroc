import logging
from datetime import UTC, datetime

import requests
from dotenv import load_dotenv

from meteo.config import CITIES, HOURLY_FIELDS
from meteo.database import connect_db, load_rows
from meteo.extract import request_json_with_retry
from meteo.transform import transform
from storage import (
    ensure_bucket,
    get_s3_client,
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

REQUEST_TIMEOUT = 30



# ============================================================
# 2. EXTRACTION - OPEN-METEO API
# ============================================================



def extract(session, city, latitude, longitude):
    """Extraire les prévisions météo pour une ville."""

    params = {
        "latitude": latitude,
        "longitude": longitude,
        "hourly": ",".join(HOURLY_FIELDS),
        "timezone": "GMT",
        "timeformat": "unixtime",
        "forecast_days": 1,
    }

    return request_json_with_retry(
        session=session,
        url=API_URL,
        params=params,
        timeout=REQUEST_TIMEOUT,
        context=city,
    )


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
# 5. POSTGRESQL UPSERT
# ============================================================


def load(rows):
    """Charger les observations météo dans PostgreSQL."""

    if not rows:
        return 0

    with connect_db() as conn:
        return load_rows(conn, rows, "weather_observations")



# ============================================================
# 6. PIPELINE ORCHESTRATION
# ============================================================


def main():

    successful_cities = 0
    failed_cities = 0
    total_rows = 0

    run_date = datetime.now(UTC).date().isoformat()

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

        logger.info("DATA LAKE READY | bucket=meteo-raw")

    except Exception:
        logger.exception("DATA LAKE UNAVAILABLE | pipeline stopped")
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

                logger.info(
                    "TRANSFORM | %s | %s observations",
                    city,
                    len(rows),
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
