# Météo Maroc

A Python-based Data Engineering project for collecting, transforming, and storing weather data for Moroccan cities.

## 1. Project Overview

Météo Maroc implements weather data ingestion pipelines using the Open-Meteo API.

The project includes:
- A weather ingestion pipeline.
- A historical weather ingestion pipeline.
- PostgreSQL for structured weather data.
- SeaweedFS for raw JSON storage in the main pipeline.
- Docker Compose for local infrastructure.
- Automated transformation tests using pytest.

## 2. Architecture

**Main pipeline:**

Open-Meteo API → Python extraction → SeaweedFS (raw JSON) → Python transformation → PostgreSQL

**Historical pipeline:**

Open-Meteo API → Python extraction → Python transformation → PostgreSQL

The historical pipeline does not currently store raw JSON in SeaweedFS.

## 3. Prerequisites

Install the following tools:

- Docker Desktop with Docker Compose
- Python 3.12 or newer
- uv (Python package and environment manager)
- Git

## 4. Installation

Clone the repository:

```bash
git clone https://github.com/mehdi98-jad/meteo-maroc.git
cd meteo-maroc
```

Create your local environment configuration:

```bash
cp .env.example .env
```

Edit `.env` and configure the PostgreSQL and S3 connection settings.

The `.env` file is excluded from Git and must not contain credentials that are committed to the repository.

Install Python dependencies:

```bash
uv sync
```

## 5. Start the Infrastructure

Start PostgreSQL and SeaweedFS:

```bash
docker compose up -d
```

Check the services:

```bash
docker compose ps
```

On a newly initialized PostgreSQL data volume, the SQL scripts in the `sql/` directory automatically create the required tables.

The initialization scripts run only when PostgreSQL initializes a new data directory.

**Important:** Do not use `docker compose down -v` unless you intentionally want to delete the persistent data volumes.

## 6. Run the Pipelines

Run the main weather ingestion pipeline:

```bash
uv run python pipeline.py
```

Run the historical ingestion pipeline:

```bash
uv run python pipeline_historique.py
```

The main pipeline stores raw JSON in SeaweedFS before loading transformed records into PostgreSQL.

The historical pipeline loads transformed historical weather data into PostgreSQL.

Both pipelines report failures through their logs and return a nonzero exit code when processing failures occur.

## 7. Run Tests

Run automated tests:

```bash
uv run pytest -v
```

Check Python code quality:

```bash
uv run ruff check .
```

The existing automated tests primarily cover weather data transformation.

## 8. Project Structure

```text
meteo-maroc/
├── docker-compose.yml
├── pipeline.py
├── pipeline_historique.py
├── storage.py
├── pyproject.toml
├── uv.lock
├── .env.example
├── sql/
│   ├── 001_create_weather_observations.sql
│   └── 002_create_weather_history.sql
└── tests/
    └── test_transform.py
```

## 9. Current Limitations

- Forecast and historical data are stored in separate PostgreSQL tables, but the distinction between forecasts and observations requires further architectural review.
- The historical pipeline does not yet store raw API responses in the data lake.
- The pipeline implementations contain duplicated code.
- Raw JSON object naming and immutability require improvements.
- Further integration tests are needed.

## 10. Planned Improvements

- Refactor the pipelines into shared Python modules.
- Improve raw data naming and storage consistency.
- Add more unit and integration tests.
- Introduce orchestration and monitoring.
