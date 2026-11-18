from unittest.mock import Mock

import pytest

from storage import city_to_slug, save_raw_json


@pytest.mark.parametrize(
    "city, expected",
    [
        ("Fès", "fes"),
        ("Meknès", "meknes"),
        ("Tétouan", "tetouan"),
        ("Casablanca", "casablanca"),
        ("Béni Mellal", "beni-mellal"),
        ("El Jadida", "el-jadida"),
        ("  Rabat  ", "rabat"),
    ],
)
def test_city_to_slug(city, expected):
    assert city_to_slug(city) == expected

def test_save_raw_json_uses_normalized_city_slug():
    client = Mock()

    key = save_raw_json(
        client=client,
        city="Fès",
        data={"temperature": 22},
        run_date="2026-11-18",
    )

    expected_key = (
        "source=open-meteo/date=2026-11-18/"
        "city=fes/forecast.json"
    )

    assert key == expected_key

    client.put_object.assert_called_once()

    arguments = client.put_object.call_args.kwargs

    assert arguments["Key"] == expected_key
    assert arguments["ContentType"] == "application/json"
