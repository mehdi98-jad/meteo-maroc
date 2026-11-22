
"""Gestion commune des requêtes HTTP vers Open-Meteo."""

import logging
import time

import requests

from meteo.config import MAX_RETRIES

logger = logging.getLogger(__name__)


def request_json_with_retry(
    session,
    url,
    params,
    timeout,
    context,
):
    """Effectuer une requête GET avec retries et backoff exponentiel."""

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logger.info(
                "EXTRACT | %s | tentative %s/%s",
                context,
                attempt,
                MAX_RETRIES,
            )

            response = session.get(
                url,
                params=params,
                timeout=timeout,
            )

            response.raise_for_status()

            return response.json()

        except (requests.RequestException, ValueError) as exc:
            status_code = (
                exc.response.status_code
                if isinstance(exc, requests.HTTPError)
                and exc.response is not None
                else None
            )

            retryable = (
                status_code is None
                or status_code == 429
                or status_code >= 500
            )

            if not retryable or attempt == MAX_RETRIES:
                raise

            delay = 2**attempt

            logger.warning(
                "RETRY | %s | %s | attente %ss",
                context,
                exc,
                delay,
            )

            time.sleep(delay)
