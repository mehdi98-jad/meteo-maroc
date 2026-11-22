
from unittest.mock import MagicMock, patch

import pipeline
import pipeline_historique


def test_forecast_extract_uses_correct_parameters():
    session = MagicMock()
    expected_data = {"hourly": {"time": []}}

    with patch(
        "pipeline.request_json_with_retry",
        return_value=expected_data,
    ) as mock_request:
        result = pipeline.extract(
            session,
            "Fès",
            34.06,
            -4.98,
        )

    assert result == expected_data

    mock_request.assert_called_once_with(
        session=session,
        url="https://api.open-meteo.com/v1/forecast",
        params={
            "latitude": 34.06,
            "longitude": -4.98,
            "hourly": (
                "temperature_2m,relative_humidity_2m,"
                "precipitation,wind_speed_10m"
            ),
            "timezone": "GMT",
            "timeformat": "unixtime",
            "forecast_days": 1,
        },
        timeout=30,
        context="Fès",
    )


def test_historical_extract_uses_correct_parameters():
    session = MagicMock()
    expected_data = {"hourly": {"time": []}}

    with patch(
        "pipeline_historique.request_json_with_retry",
        return_value=expected_data,
    ) as mock_request:
        result = pipeline_historique.extract(
            session,
            "Fès",
            34.06,
            -4.98,
            "2026-01-01",
            "2026-01-31",
        )

    assert result == expected_data

    mock_request.assert_called_once_with(
        session=session,
        url="https://archive-api.open-meteo.com/v1/archive",
        params={
            "latitude": 34.06,
            "longitude": -4.98,
            "start_date": "2026-01-01",
            "end_date": "2026-01-31",
            "hourly": (
                "temperature_2m,relative_humidity_2m,"
                "precipitation,wind_speed_10m"
            ),
            "timezone": "GMT",
            "timeformat": "unixtime",
        },
        timeout=60,
        context="Fès | 2026-01-01 -> 2026-01-31",
    )
