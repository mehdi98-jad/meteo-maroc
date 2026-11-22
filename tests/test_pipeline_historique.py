
from unittest.mock import MagicMock, patch

import pytest

from pipeline_historique import main


def test_main_reuses_connection_and_continues_after_failure():
    months = [
        ("2026-01-01", "2026-01-31"),
        ("2026-02-01", "2026-02-28"),
        ("2026-03-01", "2026-03-31"),
    ]

    cities = {"Fès": (34.06, -4.98)}

    # Une connexion PostgreSQL simulée.
    connection = MagicMock()

    with (
        patch("pipeline_historique.CITIES", cities),
        patch(
            "pipeline_historique.generate_months",
            return_value=iter(months),
        ),
        patch("pipeline_historique.requests.Session"),
        patch("pipeline_historique.connect_db") as mock_connect,
        patch(
            "pipeline_historique.extract",
            return_value={"hourly": {}},
        ) as mock_extract,
        patch(
            "pipeline_historique.transform",
            return_value=[("test-row",)],
        ),
        patch(
            "pipeline_historique.load_rows",
            side_effect=[
                1,
                RuntimeError("Erreur PostgreSQL simulée"),
                1,
            ],
        ) as mock_load,
    ):
        mock_connect.return_value.__enter__.return_value = connection

        # Un lot échoue : main() doit terminer avec le code 1.
        with pytest.raises(SystemExit) as exc_info:
            main()

    assert exc_info.value.code == 1

    # Une seule ouverture de connexion pour les trois mois.
    mock_connect.assert_called_once_with()

    # Les trois mois ont bien été traités.
    assert mock_extract.call_count == 3
    assert mock_load.call_count == 3

    # Tous les chargements utilisent la même connexion.
    for call in mock_load.call_args_list:
        assert call.args[0] is connection
        assert call.args[2] == "weather_history"

    # La connexion est fermée à la sortie du contexte.
    mock_connect.return_value.__exit__.assert_called_once()
