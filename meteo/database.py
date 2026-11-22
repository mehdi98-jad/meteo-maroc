
"""Gestion partagée des connexions et chargements PostgreSQL."""

import os

import psycopg
from psycopg import sql

ALLOWED_TABLES = {
    "weather_observations",
    "weather_history",
}


def connect_db():
    """Ouvrir une connexion PostgreSQL réutilisable."""

    return psycopg.connect(
        host=os.getenv("POSTGRES_HOST", "127.0.0.1"),
        port=int(os.getenv("POSTGRES_PORT", "5433")),
        dbname=os.environ["POSTGRES_DB"],
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
        connect_timeout=10,
        autocommit=True,
    )


def load_rows(conn, rows, table):
    """Insérer un lot dans une transaction indépendante."""

    if table not in ALLOWED_TABLES:
        raise ValueError(f"Table non autorisée : {table}")

    if not rows:
        return 0

    query = sql.SQL("""
        INSERT INTO {} (
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
            wind_speed_kmh = EXCLUDED.wind_speed_kmh
    """).format(sql.Identifier(table))

    with conn.transaction(), conn.cursor() as cur:
        cur.executemany(query, rows)

    return len(rows)
