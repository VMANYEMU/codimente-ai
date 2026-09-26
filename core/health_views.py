"""
Health check endpoint.

Load balancers and external uptime monitors need a cheap,
unauthenticated endpoint that answers two questions: is the
process alive, and can it reach the database.

The database probe result is cached briefly so a monitor
polling every minute does not add constant query load.
"""

import logging
import time

from django.db import connection
from django.http import JsonResponse

logger = logging.getLogger(__name__)


HEALTH_CACHE_SECONDS = 60

_health_state = {
    "checked_at": 0.0,
    "status": None,
    "database": None,
}


def _probe_database():

    try:

        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")

        return True

    except Exception:

        # Never leak exception details on an
        # unauthenticated endpoint; log them instead.

        logger.warning(
            "Health check: database query failed.",
            exc_info=True,
        )

        return False


def _respond(state):

    return JsonResponse(
        state,
        status=200 if state["status"] == "ok" else 503,
    )


def health(request):

    now = time.time()

    if (
        _health_state["status"] is not None
        and now - _health_state["checked_at"]
        < HEALTH_CACHE_SECONDS
    ):

        return _respond(_health_state)

    database_ok = _probe_database()

    state = {
        "checked_at": now,
        "status": "ok" if database_ok else "degraded",
        "database": "ok" if database_ok else "unavailable",
    }

    _health_state.clear()
    _health_state.update(state)

    return _respond(state)
