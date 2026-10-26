from datetime import UTC, datetime

import pytest

from pipeline import transform


@pytest.fixture
def sample_weather_data():
    """Données Open-Meteo fictives pour les tests."""
    return {
        "hourly": {
            "time": [1760918400, 1760922000],
            "temperature_2m": [22.5, 23.1],
            "relative_humidity_2m": [65, 70],
            "precipitation": [0.0, 1.2],
            "wind_speed_10m": [12.5, 15.0],
        }
    }


def test_transform_returns_correct_number_of_rows(sample_weather_data):
    rows = transform("Casablanca", sample_weather_data)

    assert len(rows) == 2


def test_transform_preserves_city(sample_weather_data):
    rows = transform("Casablanca", sample_weather_data)

    assert all(row[0] == "Casablanca" for row in rows)


def test_transform_converts_unix_timestamp(sample_weather_data):
    rows = transform("Casablanca", sample_weather_data)

    expected = datetime.fromtimestamp(
        1760918400,
        tz=UTC,
    )

    assert rows[0][1] == expected
    assert rows[0][1].tzinfo == UTC


def test_transform_preserves_weather_values(sample_weather_data):
    rows = transform("Casablanca", sample_weather_data)

    assert rows[0][2:] == (22.5, 65, 0.0, 12.5)
    assert rows[1][2:] == (23.1, 70, 1.2, 15.0)


def test_transform_rejects_inconsistent_lengths(sample_weather_data):
    sample_weather_data["hourly"]["temperature_2m"] = [22.5]

    with pytest.raises(ValueError, match="incohérentes"):
        transform("Casablanca", sample_weather_data)


def test_transform_handles_empty_hourly_data():
    data = {
        "hourly": {
            "time": [],
            "temperature_2m": [],
            "relative_humidity_2m": [],
            "precipitation": [],
            "wind_speed_10m": [],
        }
    }

    assert transform("Casablanca", data) == []


def test_transform_preserves_missing_measurements(sample_weather_data):
    sample_weather_data["hourly"]["temperature_2m"][0] = None

    rows = transform("Casablanca", sample_weather_data)

    assert rows[0][2] is None
