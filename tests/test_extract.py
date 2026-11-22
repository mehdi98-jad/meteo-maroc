
from unittest.mock import MagicMock, call, patch

import pytest
import requests

from meteo.extract import request_json_with_retry

URL = "https://api.open-meteo.com/v1/forecast"
PARAMS = {"latitude": 34.06, "longitude": -4.98}


def make_response(status_code, payload=None):
    """Construire une fausse réponse HTTP."""
    response = requests.Response()
    response.status_code = status_code
    response.url = URL

    if payload is not None:
        import json

        response._content = json.dumps(payload).encode("utf-8")

    return response


def test_success_on_first_attempt():
    session = MagicMock()
    session.get.return_value = make_response(
        200, {"hourly": {"time": [123]}}
    )

    with patch("meteo.extract.time.sleep") as mock_sleep:
        result = request_json_with_retry(
            session, URL, PARAMS, 30, "Fès"
        )

    assert result == {"hourly": {"time": [123]}}
    session.get.assert_called_once_with(
        URL, params=PARAMS, timeout=30
    )
    mock_sleep.assert_not_called()


def test_retry_on_http_500():
    session = MagicMock()
    session.get.side_effect = [
        make_response(500),
        make_response(500),
        make_response(200, {"success": True}),
    ]

    with patch("meteo.extract.time.sleep") as mock_sleep:
        result = request_json_with_retry(
            session, URL, PARAMS, 30, "Fès"
        )

    assert result == {"success": True}
    assert session.get.call_count == 3
    assert mock_sleep.call_args_list == [call(2), call(4)]


def test_retry_on_http_429():
    session = MagicMock()
    session.get.side_effect = [
        make_response(429),
        make_response(200, {"success": True}),
    ]

    with patch("meteo.extract.time.sleep") as mock_sleep:
        result = request_json_with_retry(
            session, URL, PARAMS, 30, "Fès"
        )

    assert result == {"success": True}
    assert session.get.call_count == 2
    mock_sleep.assert_called_once_with(2)


def test_no_retry_on_http_404():
    session = MagicMock()
    session.get.return_value = make_response(404)

    with (
        patch("meteo.extract.time.sleep") as mock_sleep,
        pytest.raises(requests.HTTPError),
    ):
        request_json_with_retry(
            session, URL, PARAMS, 30, "Fès"
        )

    assert session.get.call_count == 1
    mock_sleep.assert_not_called()


def test_retry_on_network_error():
    session = MagicMock()
    session.get.side_effect = [
        requests.ConnectionError("Connection lost"),
        make_response(200, {"success": True}),
    ]

    with patch("meteo.extract.time.sleep") as mock_sleep:
        result = request_json_with_retry(
            session, URL, PARAMS, 30, "Fès"
        )

    assert result == {"success": True}
    assert session.get.call_count == 2
    mock_sleep.assert_called_once_with(2)


def test_retry_on_invalid_json():
    session = MagicMock()
    session.get.side_effect = [
        make_response(200),
        make_response(200, {"success": True}),
    ]

    with patch("meteo.extract.time.sleep") as mock_sleep:
        result = request_json_with_retry(
            session, URL, PARAMS, 30, "Fès"
        )

    assert result == {"success": True}
    assert session.get.call_count == 2
    mock_sleep.assert_called_once_with(2)


def test_raises_after_three_failures():
    session = MagicMock()
    session.get.return_value = make_response(503)

    with (
        patch("meteo.extract.time.sleep") as mock_sleep,
        pytest.raises(requests.HTTPError),
    ):
        request_json_with_retry(
            session, URL, PARAMS, 30, "Fès"
        )

    assert session.get.call_count == 3
    assert mock_sleep.call_args_list == [call(2), call(4)]
