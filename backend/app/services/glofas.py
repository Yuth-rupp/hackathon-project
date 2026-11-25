"""
FloodPulse AI - GloFAS discharge service (single source of truth)

Why this module exists
----------------------
River discharge used to be written by TWO different code paths (the scheduler
and the /hydrology/discharge route) with different windows (14 vs 17 days) and
different source labels. Whichever wrote last "won", so the Hydrology page
flipped between runs. Both now call store_glofas_forecast() below.

It also provides the REAL reference baseline. Open-Meteo's river_discharge_mean
/ _median / _max are statistics of the forecast ensemble itself, not a
historical normal, so comparing a forecast with them always gave ~0%. Here the
baseline is built from the 1991-2020 GloFAS archive, per location and per
day-of-year.

Caveat: the archive is GloFAS reanalysis while recent values come from the
forecast model, so small systematic differences are possible. Read results as
"relative to the usual range for this time of year", not as exact anomalies.
"""

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import aiosqlite
import httpx

from app.config import settings
from app.services.realtime import broker

logger = logging.getLogger(__name__)

FLOOD_API_URL = (
    getattr(settings, "OPEN_METEO_FLOOD_URL", None)
    or "https://flood-api.open-meteo.com/v1/flood"
)

# One canonical label + window for every writer of river_discharge.
DISCHARGE_SOURCE_LABEL = "Open-Meteo GloFAS v4"
DISCHARGE_PAST_DAYS = 3
DISCHARGE_FORECAST_DAYS = 14
DISCHARGE_DAILY_VARS = (
    "river_discharge,river_discharge_mean,river_discharge_median,river_discharge_max"
)

CLIMATOLOGY_START = "1991-01-01"   # standard 30-year climatological normal
CLIMATOLOGY_END = "2020-12-31"
CLIMATOLOGY_WINDOW_DAYS = 7        # +/- days pooled around each day-of-year
CLIMATOLOGY_MIN_SAMPLES = 30
CLIMATOLOGY_REFRESH_DAYS = 30
CLIMATOLOGY_LABEL = f"{CLIMATOLOGY_START[:4]}-{CLIMATOLOGY_END[:4]} same-season climatology"


def _num(value: Any) -> Optional[float]:
    """Float or None. Missing values are never turned into 0."""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


# ==============================================================================
# Forecast fetch + store (used by BOTH the scheduler and the API route)
# ==============================================================================

async def store_glofas_forecast(
    db: aiosqlite.Connection,
    location_id: int,
    lat: float,
    lon: float,
    client: Optional[httpx.AsyncClient] = None,
) -> Dict[str, Any]:
    """
    Fetch the GloFAS discharge window for one location and store it.
    RAISES on any failure (so callers can report the real reason) and never
    overwrites good rows with an all-empty response.

    Returns {"retrieval_timestamp": iso, "records": n}.
    """
    params = {
        "latitude": lat,
        "longitude": lon,
        "daily": DISCHARGE_DAILY_VARS,
        "past_days": DISCHARGE_PAST_DAYS,
        "forecast_days": DISCHARGE_FORECAST_DAYS,
    }

    if client is None:
        async with httpx.AsyncClient(timeout=20.0) as own_client:
            response = await own_client.get(FLOOD_API_URL, params=params)
    else:
        response = await client.get(FLOOD_API_URL, params=params)
    response.raise_for_status()

    daily = response.json().get("daily") or {}
    dates = daily.get("time") or []
    discharges = daily.get("river_discharge") or []
    means = daily.get("river_discharge_mean") or []
    medians = daily.get("river_discharge_median") or []
    maxes = daily.get("river_discharge_max") or []

    if not dates:
        raise ValueError("GloFAS returned no dates")
    if all(_num(v) is None for v in discharges):
        raise ValueError("GloFAS returned no discharge values for these coordinates")

    def at(values: List[Any], index: int) -> Optional[float]:
        return _num(values[index]) if index < len(values) else None

    now_iso = datetime.now(timezone.utc).isoformat()

    try:
        for index, day in enumerate(dates):
            # Replace (never accumulate) this source's row for the same day.
            await db.execute(
                """
                DELETE FROM river_discharge
                WHERE location_id = ? AND date = ? AND data_source = ?
                """,
                (location_id, day, DISCHARGE_SOURCE_LABEL),
            )
            await db.execute(
                """
                INSERT INTO river_discharge (
                    location_id, date, discharge_m3s, discharge_max,
                    discharge_mean, discharge_median, data_source,
                    retrieval_timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    location_id,
                    day,
                    at(discharges, index),
                    at(maxes, index),
                    at(means, index),
                    at(medians, index),
                    DISCHARGE_SOURCE_LABEL,
                    now_iso,
                ),
            )
        await db.commit()
    except Exception:
        await db.rollback()
        raise

    try:
        broker.publish("discharge_updated", {"location_id": location_id})
    except Exception:  # broadcasting must never break ingestion
        logger.warning("Could not publish discharge_updated", exc_info=True)

    return {"retrieval_timestamp": now_iso, "records": len(dates)}


# ==============================================================================
# Climatology: the real "reference" for discharge
# ==============================================================================

def _percentile(sorted_values: List[float], q: float) -> float:
    """Linear-interpolated percentile of an already sorted list (0 <= q <= 1)."""
    position = (len(sorted_values) - 1) * q
    lower = int(position)
    upper = min(lower + 1, len(sorted_values) - 1)
    return sorted_values[lower] + (sorted_values[upper] - sorted_values[lower]) * (position - lower)


def build_climatology(
    dates: List[str],
    values: List[Optional[float]],
    window: int = CLIMATOLOGY_WINDOW_DAYS,
) -> Dict[int, Dict[str, float]]:
    """
    Per-day-of-year statistics from a long daily series, pooling +/- `window`
    days (wrapping around the year) so every day has enough samples.
    """
    by_doy: Dict[int, List[float]] = {d: [] for d in range(1, 367)}
    for day, value in zip(dates, values):
        number = _num(value)
        if number is None:
            continue
        try:
            doy = date.fromisoformat(str(day)[:10]).timetuple().tm_yday
        except ValueError:
            continue
        by_doy[doy].append(number)

    result: Dict[int, Dict[str, float]] = {}
    for doy in range(1, 367):
        pool: List[float] = []
        for offset in range(-window, window + 1):
            pool.extend(by_doy[((doy - 1 + offset) % 366) + 1])
        if len(pool) < CLIMATOLOGY_MIN_SAMPLES:
            continue
        pool.sort()
        result[doy] = {
            "mean": sum(pool) / len(pool),
            "median": _percentile(pool, 0.50),
            "p25": _percentile(pool, 0.25),
            "p75": _percentile(pool, 0.75),
            "p90": _percentile(pool, 0.90),
            "samples": float(len(pool)),
        }
    return result


async def ensure_climatology_table(db: aiosqlite.Connection) -> None:
    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS discharge_climatology (
            location_id  INTEGER NOT NULL,
            day_of_year  INTEGER NOT NULL,
            mean_m3s     REAL,
            median_m3s   REAL,
            p25_m3s      REAL,
            p75_m3s      REAL,
            p90_m3s      REAL,
            samples      INTEGER,
            period       TEXT,
            computed_at  TEXT,
            PRIMARY KEY (location_id, day_of_year)
        )
        """
    )


async def climatology_age_days(
    db: aiosqlite.Connection, location_id: int
) -> Optional[float]:
    """Age of a location's stored climatology in days, or None if there is none."""
    await ensure_climatology_table(db)
    cursor = await db.execute(
        "SELECT MAX(computed_at) FROM discharge_climatology WHERE location_id = ?",
        (location_id,),
    )
    row = await cursor.fetchone()
    if not row or not row[0]:
        return None
    try:
        computed = datetime.fromisoformat(str(row[0]).replace("Z", "+00:00"))
    except ValueError:
        return None
    if computed.tzinfo is None:
        computed = computed.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - computed).total_seconds() / 86400.0


async def refresh_location_climatology(
    db: aiosqlite.Connection,
    location_id: int,
    lat: float,
    lon: float,
    client: Optional[httpx.AsyncClient] = None,
) -> int:
    """Download the 1991-2020 archive for one location and store its climatology."""
    params = {
        "latitude": lat,
        "longitude": lon,
        "daily": "river_discharge",
        "start_date": CLIMATOLOGY_START,
        "end_date": CLIMATOLOGY_END,
    }
    if client is None:
        async with httpx.AsyncClient(timeout=60.0) as own_client:
            response = await own_client.get(FLOOD_API_URL, params=params)
    else:
        response = await client.get(FLOOD_API_URL, params=params)
    response.raise_for_status()

    daily = response.json().get("daily") or {}
    clim = build_climatology(daily.get("time") or [], daily.get("river_discharge") or [])
    if not clim:
        raise ValueError("not enough historical data to build a climatology")

    await ensure_climatology_table(db)
    computed_at = datetime.now(timezone.utc).isoformat()
    period = f"{CLIMATOLOGY_START[:4]}-{CLIMATOLOGY_END[:4]}"
    rows = [
        (
            location_id, doy, s["mean"], s["median"], s["p25"], s["p75"],
            s["p90"], int(s["samples"]), period, computed_at,
        )
        for doy, s in clim.items()
    ]
    try:
        await db.execute(
            "DELETE FROM discharge_climatology WHERE location_id = ?", (location_id,)
        )
        await db.executemany(
            """
            INSERT INTO discharge_climatology (
                location_id, day_of_year, mean_m3s, median_m3s, p25_m3s,
                p75_m3s, p90_m3s, samples, period, computed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    return len(rows)


async def get_climatology(
    db: aiosqlite.Connection, location_id: int, on_date: str
) -> Optional[Dict[str, float]]:
    """Climatology for a location on an ISO date (YYYY-MM-DD), or None."""
    try:
        doy = date.fromisoformat(str(on_date)[:10]).timetuple().tm_yday
    except ValueError:
        return None
    try:
        cursor = await db.execute(
            """
            SELECT mean_m3s, median_m3s, p25_m3s, p75_m3s, p90_m3s, samples
            FROM discharge_climatology
            WHERE location_id = ? AND day_of_year = ?
            """,
            (location_id, doy),
        )
        row = await cursor.fetchone()
    except Exception:
        return None  # table not created yet
    if not row:
        return None
    return {
        "mean": row[0], "median": row[1], "p25": row[2],
        "p75": row[3], "p90": row[4], "samples": row[5],
    }


def classify_discharge(
    value: Optional[float], clim: Optional[Dict[str, float]]
) -> Dict[str, Any]:
    """
    Compare a discharge value with the same-season historical range.
    Returns UNKNOWN (never a fake NORMAL) when there is no value or baseline.
    """
    if value is None:
        return {"classification": "UNKNOWN", "pct_vs_mean": None,
                "reference_mean": None, "basis": "no_value"}
    if not clim or clim.get("mean") is None:
        return {"classification": "UNKNOWN", "pct_vs_mean": None,
                "reference_mean": None, "basis": "no_climatology"}

    mean = clim["mean"]
    pct = round((value - mean) / mean * 100, 1) if mean else None

    if value < clim["p25"]:
        label = "LOW"
    elif value <= clim["p75"]:
        label = "NORMAL"
    elif value <= clim["p90"]:
        label = "ELEVATED"
    else:
        label = "HIGH"

    return {
        "classification": label,
        "pct_vs_mean": pct,
        "reference_mean": round(mean, 3),
        "basis": CLIMATOLOGY_LABEL,
    }


def score_discharge_vs_climatology(
    value: Optional[float], clim: Optional[Dict[str, float]]
) -> Optional[float]:
    """
    0-100 hazard score for a discharge value relative to THIS location's own
    seasonal range (scale-free, so a small stream and a big river are judged
    fairly). Typical flow (median) scores 20, p75 -> 40, p90 -> 65,
    1.5 x p90 -> 90, 2 x p90 or more -> 100.
    Returns None when no usable baseline exists (never guesses).
    """
    if value is None or not clim:
        return None
    p25, median = clim.get("p25"), clim.get("median")
    p75, p90 = clim.get("p75"), clim.get("p90")
    if None in (p25, median, p75, p90):
        return None

    anchors = [
        (0.0, 0.0), (p25, 10.0), (median, 20.0), (p75, 40.0),
        (p90, 65.0), (p90 * 1.5, 90.0), (p90 * 2.0, 100.0),
    ]
    points = [anchors[0]]
    for x, y in anchors[1:]:
        if x > points[-1][0] + 1e-9:   # drop degenerate (flat) anchors
            points.append((x, y))
    if len(points) < 2:
        return None

    v = max(0.0, float(value))
    if v >= points[-1][0]:
        return round(points[-1][1], 2)
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        if v <= x1:
            return round(y0 + (y1 - y0) * (v - x0) / (x1 - x0), 2)
    return round(points[-1][1], 2)