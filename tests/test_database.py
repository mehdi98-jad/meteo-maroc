
from unittest.mock import MagicMock

import pytest

from meteo.database import load_rows


def test_load_rows_success():
    conn = MagicMock()
    rows = [
        ("Casablanca", "2026-11-18T12:00:00Z", 22.5, 65, 0.0, 12.0),
    ]

    result = load_rows(conn, rows, "weather_observations")

    assert result == 1
    conn.transaction.assert_called_once_with()

    cursor = conn.cursor.return_value.__enter__.return_value
    cursor.executemany.assert_called_once()

    query, actual_rows = cursor.executemany.call_args.args

    assert actual_rows == rows
    assert "weather_observations" in query.as_string()


def test_load_rows_empty_batch():
    conn = MagicMock()

    result = load_rows(conn, [], "weather_history")

    assert result == 0
    conn.transaction.assert_not_called()
    conn.cursor.assert_not_called()


def test_load_rows_rejects_unauthorized_table():
    conn = MagicMock()

    with pytest.raises(ValueError, match="Table non autorisée"):
        load_rows(conn, [("test",)], "users")

    conn.transaction.assert_not_called()
    conn.cursor.assert_not_called()


def test_load_rows_propagates_sql_error():
    conn = MagicMock()

    cursor = conn.cursor.return_value.__enter__.return_value
    cursor.executemany.side_effect = RuntimeError("SQL failure")

    with pytest.raises(RuntimeError, match="SQL failure"):
        load_rows(
            conn,
            [("Casablanca", "2026-11-18", 22, 60, 0, 10)],
            "weather_history",
        )

    transaction = conn.transaction.return_value
    transaction.__exit__.assert_called_once()

    exit_args = transaction.__exit__.call_args.args

    assert exit_args[0] is RuntimeError
