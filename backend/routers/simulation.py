"""
Simulation router — GET /simulate/logs.

Returns a set of randomly selected recent event logs to let the frontend
demonstrate live-streaming / auto-refresh behaviour without needing a
real-time event pipeline.

Authentication required (any role).
"""

from __future__ import annotations

import logging
import random
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse

from database.connection import AsyncConnection, fetch_all, get_connection
from routers.dependencies import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/simulate", tags=["Simulation"])


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

_SEVERITIES = ["P1", "P2", "P3", "P4"]
_CATEGORIES = ["interface", "performance", "wireless", "connectivity", "system"]

# Pool of synthetic message templates (used when there are no DB logs)
_SYNTHETIC_MESSAGES = [
    "Interface GigabitEthernet0/1 is down",
    "High CPU utilization: 92% for 5 minutes",
    "OSPF neighbor 10.0.1.2 state change to DOWN",
    "BGP session with 192.168.1.1 reset",
    "Fan failure detected in slot 2",
    "Memory utilization exceeded 85% threshold",
    "STP topology change detected on VLAN 10",
    "SNMP authentication failure from 10.5.5.5",
    "Power supply redundancy lost",
    "QoS queue drop rate exceeded 1000 pps",
    "Wireless client de-authentication flood detected",
    "LACP PDU timeout on port-channel 1",
    "ACL deny count exceeded 500 in 60 seconds",
    "NTP synchronization lost — stratum unreachable",
    "Temperature sensor alarm: 78°C (threshold: 70°C)",
]


async def _get_random_real_logs(conn, count: int) -> list[dict]:
    """Fetch random real event_log rows from the database.

    Args:
        conn: Active database connection.
        count: Number of rows to return.

    Returns:
        List of enriched event_log row dicts.
    """
    rows = await fetch_all(
        conn,
        """
        SELECT
            el.event_id,
            el.event_time,
            el.event_type_name,
            etl.severity,
            etl.category,
            el.message,
            el.device_id,
            d.device_name,
            d.ip_address,
            el.current_status,
            el.raw_detail
        FROM event_logs el
        LEFT JOIN devices d              ON el.device_id     = d.device_id
        LEFT JOIN event_type_lookup etl  ON el.event_type_id = etl.event_type_id
        ORDER BY RANDOM()
        LIMIT ?
        """,
        (count,),
    )
    return rows


def _make_synthetic_log(idx: int) -> dict:
    """Generate a single synthetic log entry for simulation.

    Args:
        idx: Index used to seed deterministic-looking fake IDs.

    Returns:
        Synthetic log dict.
    """
    return {
        "event_id":       900_000 + idx,
        "event_time":     f"14:{idx % 60:02d}:{random.randint(0, 59):02d}.000",
        "event_type_name": random.choice(["Node Down", "Interface Down", "High CPU", "Node Up"]),
        "severity":       random.choice(_SEVERITIES),
        "category":       random.choice(_CATEGORIES),
        "message":        random.choice(_SYNTHETIC_MESSAGES),
        "device_id":      random.randint(1, 500),
        "device_name":    f"SIM-DEVICE-{random.randint(1, 100):03d}",
        "ip_address":     f"10.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(1,254)}",
        "current_status": random.choice([0, 1]),
        "raw_detail":     None,
        "simulated":      True,
    }


# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------


@router.get(
    "/logs",
    summary="Get randomly sampled event logs for frontend simulation",
    responses={
        200: {
            "description": (
                "Random selection of event log rows. "
                "Mix of real DB rows and synthetic entries if the DB has fewer rows than requested."
            )
        },
        400: {"description": "Invalid count parameter"},
        401: {"description": "Authentication required"},
        500: {"description": "Internal server error"},
    },
)
async def simulate_logs(
    current_user: Annotated[dict, Depends(get_current_user)],
    conn: AsyncConnection = Depends(get_connection),
    count: int = Query(
        default=10,
        ge=1,
        le=50,
        description="Number of random log entries to return (1–50)",
    ),
    synthetic_ratio: float = Query(
        default=0.0,
        ge=0.0,
        le=1.0,
        description=(
            "Fraction of results that should be synthetic/fake (0.0 = all real, "
            "1.0 = all synthetic). Useful for demos when the DB has few rows."
        ),
    ),
) -> JSONResponse:
    """Return a random sample of event log entries for simulation purposes.

    The response is a mix of:
    - **Real rows** randomly selected from the ``event_logs`` table.
    - **Synthetic rows** generated in-memory (flagged with ``simulated: true``).

    The ``synthetic_ratio`` parameter controls the blend. Default is ``0.0``
    (all real rows), which falls back to synthetic entries only if the DB
    returns fewer rows than requested.

    Args:
        current_user: Authenticated user (any role).
        conn: Injected database connection.
        count: Number of log entries to return.
        synthetic_ratio: Fraction of synthetic vs real rows.

    Returns:
        200 response with a shuffled list of log entries and simulation metadata.

    Raises:
        400: If count is out of range (handled by FastAPI validation).
        500: On unexpected database errors.
    """
    try:
        n_synthetic = max(0, min(count, round(count * synthetic_ratio)))
        n_real = count - n_synthetic

        # Fetch real rows
        real_rows: list[dict] = []
        if n_real > 0:
            real_rows = await _get_random_real_logs(conn, n_real)
            # If DB returned fewer rows than requested, fill remaining with synthetic
            if len(real_rows) < n_real:
                n_synthetic += n_real - len(real_rows)

        # Generate synthetic rows
        synthetic_rows = [_make_synthetic_log(i) for i in range(n_synthetic)]

        # Mark real rows without the simulated flag
        for row in real_rows:
            row["simulated"] = False  # type: ignore[assignment]

        # Shuffle combined result so real and synthetic are interleaved
        combined = real_rows + synthetic_rows
        random.shuffle(combined)

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": "OK",
                "data": combined,
                "meta": {
                    "total_returned": len(combined),
                    "real_count": len(real_rows),
                    "synthetic_count": len(synthetic_rows),
                },
            },
        )
    except Exception as exc:
        logger.error("simulate_logs error: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to generate simulated log data",
        ) from exc
