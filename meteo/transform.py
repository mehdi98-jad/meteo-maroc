"""Transformation commune des données météo Open-Meteo."""

from datetime import UTC, datetime


def transform(city, data):
    """Convertir les données horaires Open-Meteo en lignes PostgreSQL."""

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
