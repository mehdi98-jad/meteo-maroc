import calendar
import logging

import requests
from dotenv import load_dotenv

from meteo.config import CITIES, HOURLY_FIELDS
from meteo.database import connect_db, load_rows
from meteo.extract import request_json_with_retry
from meteo.transform import transform

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

REQUEST_TIMEOUT = 60



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
    """Extraire les données historiques pour une ville et une période."""

    params = {
        "latitude": latitude,
        "longitude": longitude,
        "start_date": start_date,
        "end_date": end_date,
        "hourly": ",".join(HOURLY_FIELDS),
        "timezone": "GMT",
        "timeformat": "unixtime",
    }

    return request_json_with_retry(
        session=session,
        url=API_URL,
        params=params,
        timeout=REQUEST_TIMEOUT,
        context=f"{city} | {start_date} -> {end_date}",
    )



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

    with (
        requests.Session() as session,
        connect_db() as conn,
    ):
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

                    loaded = load_rows(
                        conn,
                        rows,
                        "weather_history",
                    )

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
