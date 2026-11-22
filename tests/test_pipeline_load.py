
from unittest.mock import MagicMock, patch

from pipeline import load


def test_load_calls_shared_database_module():
    rows = [
        ("Casablanca", "2026-11-18T12:00:00Z", 22.5, 65, 0.0, 12.0),
    ]

    connection = MagicMock()
    connection_manager = MagicMock()
    connection_manager.__enter__.return_value = connection

    with (
        patch("pipeline.connect_db", return_value=connection_manager) as mock_connect,
        patch("pipeline.load_rows", return_value=1) as mock_load,
    ):
        result = load(rows)

    assert result == 1
    mock_connect.assert_called_once_with()
    mock_load.assert_called_once_with(
        connection,
        rows,
        "weather_observations",
    )
    connection_manager.__exit__.assert_called_once()


def test_load_empty_batch_does_not_connect():
    with patch("pipeline.connect_db") as mock_connect:
        result = load([])

    assert result == 0
    mock_connect.assert_not_called()
