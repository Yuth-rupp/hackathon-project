"""
FloodPulse AI - Live Community Risk

Combines every live part of the platform into one picture per province:

    risk engine    -> latest flood risk score, category, drivers, trend
    hydrology      -> gauge readings vs alarm / flood levels (live data only)
    discharge      -> current and 7-day peak river discharge
    alerts         -> active or acknowledged alerts for the province
    satellite      -> latest Sentinel-1 pass and water extent (basin level)
    community data -> population, vulnerable communes, safe sites

From these it derives ONE community action level and the posture of each safe
site (shelter, health centre, embankment). The action level follows the same
rules as /risk/thresholds:

    Low        Continue routine monitoring
    Moderate   Monitor rainfall and river conditions regularly
    High       Prepare response resources and alert vulnerable communities
    Very High  Prioritise emergency response and assess evacuation needs

Nothing here is invented: a gauge only escalates the level when its reading is
live (not a baseline placeholder, not stale), and every escalation is reported
in ``action.driven_by`` so the UI can show WHY the level is what it is.
"""

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import aiosqlite

from app.services.risk_engine import risk_engine

logger = logging.getLogger(__name__)

LEVEL_CATEGORIES = ["Low", "Moderate", "High", "Very High"]
LEVEL_KEYS = ["low", "moderate", "high", "very_high"]

ACTIONS = [
    {
        "code": "routine",
        "label_en": "Routine monitoring",
        "label_km": "ការតាមដានធម្មតា",
        "guidance_en": "Continue routine monitoring. Keep evacuation plans and contact lists up to date.",
    },
    {
        "code": "prepare",
        "label_en": "Prepare communities",
        "label_km": "រៀបចំសហគមន៍",
        "guidance_en": "Monitor rainfall and river conditions regularly. Check boats, fuel, emergency kits and safe-site access.",
    },
    {
        "code": "alert",
        "label_en": "Alert vulnerable communities",
        "label_km": "ជូនដំណឹងសហគមន៍ងាយរងគ្រោះ",
        "guidance_en": "Prepare flood response resources and alert vulnerable communities. Move livestock, grain and equipment to high ground.",
    },
    {
        "code": "evacuate",
        "label_en": "Assess / start evacuation",
        "label_km": "វាយតម្លៃ និងចាប់ផ្តើមជម្លៀស",
        "guidance_en": "Prioritise emergency response and assess evacuation needs. Follow instructions from NCDM and provincial authorities. Hotline 1294.",
    },
]

SITE_POSTURES = {
    "shelter": [
        {"code": "standby", "label_en": "Routine standby", "label_km": "ត្រៀមខ្លួនធម្មតា"},
        {"code": "prepare", "label_en": "Prepare to receive evacuees", "label_km": "រៀបចំត្រៀមទទួលជនភៀសខ្លួន"},
        {"code": "ready", "label_en": "Ready to open", "label_km": "ត្រៀមបើកទទួល"},
        {"code": "open", "label_en": "Open for evacuees", "label_km": "បើកទទួលជនភៀសខ្លួន"},
    ],
    "health": [
        {"code": "routine", "label_en": "Routine readiness", "label_km": "ការត្រៀមខ្លួនធម្មតា"},
        {"code": "stock", "label_en": "Check emergency stock", "label_km": "ពិនិត្យស្តុកសង្គ្រោះបន្ទាន់"},
        {"code": "surge_prep", "label_en": "Prepare surge capacity", "label_km": "រៀបចំសមត្ថភាពបន្ថែម"},
        {"code": "surge", "label_en": "Surge capacity active", "label_km": "សមត្ថភាពបន្ថែមកំពុងដំណើរការ"},
    ],
    "structure": [
        {"code": "routine", "label_en": "Routine inspection", "label_km": "ត្រួតពិនិត្យតាមកាលកំណត់"},
        {"code": "inspect", "label_en": "Inspect structure", "label_km": "ពិនិត្យសំណង់"},
        {"code": "patrol", "label_en": "Patrol and monitor", "label_km": "ល្បាត និងតាមដាន"},
        {"code": "emergency", "label_en": "Emergency patrol", "label_km": "ល្បាតបន្ទាន់"},
    ],
}

FACTOR_LABELS = {
    "rainfall": "Rainfall",
    "hydrology": "River & lake hydrology",
    "soil": "Soil saturation",
    "seasonal": "Seasonal timing",
    "historical": "Historical flood record",
}

# Assessments are produced every ~15 minutes.
ASSESSMENT_FRESH_MINUTES = 45
ASSESSMENT_DELAYED_MINUTES = 180

TREND_WINDOW_HOURS = 6
TREND_DELTA_POINTS = 3.0
HISTORY_HOURS = 48
HISTORY_MAX_POINTS = 24


# ---------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------

def level_index(value: Any) -> int:
    """Map any severity / category text to 0..3, or -1 when unknown."""
    text = str(value or "").strip().lower().replace("_", " ").replace("-", " ")
    mapping = {
        "low": 0, "info": 0,
        "moderate": 1, "medium": 1, "advisory": 1,
        "high": 2, "warning": 2,
        "very high": 3, "severe": 3, "critical": 3, "emergency": 3,
    }
    return mapping.get(text, -1)


def _safe_json(value: Optional[str]) -> Dict[str, Any]:
    if not value:
        return {}
    try:
        result = json.loads(value)
        return result if isinstance(result, dict) else {}
    except (json.JSONDecodeError, TypeError):
        return {}


def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _site_group(site_type: str) -> str:
    if site_type in ("safe_mound", "evacuation_center", "school"):
        return "shelter"
    if site_type == "health_center":
        return "health"
    return "structure"


def slugify(name: str) -> str:
    return name.strip().lower().replace(" ", "-").replace("_", "-")


# ---------------------------------------------------------------------
# Per-source readers
# ---------------------------------------------------------------------

async def _latest_assessment(db: aiosqlite.Connection, location_id: int):
    cursor = await db.execute(
        """
        SELECT id, assessment_date, risk_probability, risk_category,
               model_version, contributing_factors_json, confidence_info_json
        FROM risk_assessments
        WHERE location_id = ?
        ORDER BY id DESC
        LIMIT 1
        """,
        (location_id,),
    )
    return await cursor.fetchone()


async def _risk_history(
    db: aiosqlite.Connection, location_id: int, now: datetime
) -> Dict[str, Any]:
    since = (now - timedelta(hours=HISTORY_HOURS)).isoformat()
    cursor = await db.execute(
        """
        SELECT assessment_date, risk_probability
        FROM risk_assessments
        WHERE location_id = ? AND assessment_date >= ?
        ORDER BY assessment_date ASC
        """,
        (location_id, since),
    )
    rows = await cursor.fetchall()

    series = [
        (_parse_dt(r["assessment_date"]), float(r["risk_probability"]))
        for r in rows
        if _parse_dt(r["assessment_date"]) is not None
    ]

    if len(series) > HISTORY_MAX_POINTS:
        step = len(series) / HISTORY_MAX_POINTS
        series = [series[int(i * step)] for i in range(HISTORY_MAX_POINTS - 1)] + [series[-1]]

    points = [{"t": t.isoformat(), "score": round(s, 1)} for t, s in series]

    direction, delta = "unknown", None
    if len(rows) >= 2:
        latest_dt = _parse_dt(rows[-1]["assessment_date"])
        latest_score = float(rows[-1]["risk_probability"])
        cutoff = latest_dt - timedelta(hours=TREND_WINDOW_HOURS) if latest_dt else None

        reference = None
        for r in rows:
            r_dt = _parse_dt(r["assessment_date"])
            if r_dt and cutoff and r_dt <= cutoff:
                reference = float(r["risk_probability"])  # newest row at or before cutoff
        if reference is not None:
            delta = round(latest_score - reference, 1)
            if delta >= TREND_DELTA_POINTS:
                direction = "rising"
            elif delta <= -TREND_DELTA_POINTS:
                direction = "falling"
            else:
                direction = "steady"

    return {
        "direction": direction,
        "delta": delta,
        "window_hours": TREND_WINDOW_HOURS,
        "points": points,
    }


async def _province_gauges(
    db: aiosqlite.Connection, province: str
) -> List[Dict[str, Any]]:
    # Reuse the hydrology page's own rules so both pages always agree.
    from app.routers.hydrology import _freshness, _station_status

    cursor = await db.execute(
        """
        SELECT id, code, name, name_km, alarm_level, flood_level
        FROM stations
        WHERE is_active = 1 AND LOWER(province) = LOWER(?)
        ORDER BY id ASC
        """,
        (province,),
    )
    stations = await cursor.fetchall()

    gauges: List[Dict[str, Any]] = []
    for st in stations:
        r_cursor = await db.execute(
            """
            SELECT value, timestamp, data_source
            FROM water_levels
            WHERE station_id = ?
            ORDER BY timestamp DESC
            LIMIT 1
            """,
            (st["id"],),
        )
        reading = await r_cursor.fetchone()

        level = float(reading["value"]) if reading else None
        timestamp = reading["timestamp"] if reading else None
        source = reading["data_source"] if reading else None

        freshness, age_seconds = _freshness(source, timestamp)
        status = _station_status(level, st["alarm_level"], st["flood_level"])

        gauges.append(
            {
                "code": st["code"],
                "name": st["name"],
                "name_km": st["name_km"],
                "water_level_m": level,
                "alarm_level_m": st["alarm_level"],
                "flood_level_m": st["flood_level"],
                "status": status,
                "freshness": freshness,
                "age_seconds": age_seconds,
                "timestamp": timestamp,
                # Only a real, recent measurement may raise the community level.
                "counts_for_risk": freshness in ("live", "delayed"),
            }
        )
    return gauges


async def _province_alerts(
    db: aiosqlite.Connection, province: str
) -> List[Dict[str, Any]]:
    cursor = await db.execute(
        """
        SELECT id, severity, title, title_km, message, message_km,
               status, trigger_source, created_at
        FROM alerts
        WHERE LOWER(province) = LOWER(?)
          AND LOWER(status) IN ('active', 'acknowledged')
        ORDER BY id DESC
        LIMIT 5
        """,
        (province,),
    )
    return [
        {
            "id": r["id"],
            "severity": r["severity"],
            "title": r["title"],
            "title_km": r["title_km"],
            "message": r["message"],
            "message_km": r["message_km"],
            "status": r["status"],
            "trigger_source": r["trigger_source"],
            "created_at": r["created_at"],
        }
        for r in await cursor.fetchall()
    ]


async def _discharge(
    db: aiosqlite.Connection, location_id: int, now: datetime
) -> Dict[str, Any]:
    # Open-Meteo dates are local (UTC+7).
    today = (now + timedelta(hours=risk_engine.LOCAL_UTC_OFFSET_HOURS)).date()
    today_iso = today.isoformat()
    week_iso = (today + timedelta(days=7)).isoformat()

    cursor = await db.execute(
        """
        SELECT substr(date, 1, 10) AS day, discharge_m3s, data_source, retrieval_timestamp
        FROM river_discharge
        WHERE location_id = ? AND substr(date, 1, 10) <= ? AND discharge_m3s IS NOT NULL
        ORDER BY date DESC, id DESC
        LIMIT 1
        """,
        (location_id, today_iso),
    )
    current = await cursor.fetchone()

    cursor = await db.execute(
        """
        SELECT substr(date, 1, 10) AS day, discharge_m3s
        FROM river_discharge
        WHERE location_id = ? AND substr(date, 1, 10) > ? AND substr(date, 1, 10) <= ?
              AND discharge_m3s IS NOT NULL
        ORDER BY discharge_m3s DESC
        LIMIT 1
        """,
        (location_id, today_iso, week_iso),
    )
    peak = await cursor.fetchone()

    def status(value: Optional[float]) -> str:
        if value is None:
            return "no_data"
        if value >= risk_engine.DISCHARGE_ALARM_M3S:
            return "alarm"
        if value >= risk_engine.DISCHARGE_WARNING_M3S:
            return "warning"
        return "normal"

    current_value = float(current["discharge_m3s"]) if current else None
    peak_value = float(peak["discharge_m3s"]) if peak else None

    return {
        "current_m3s": current_value,
        "current_date": current["day"] if current else None,
        "current_status": status(current_value),
        "forecast_peak_m3s": peak_value,
        "forecast_peak_date": peak["day"] if peak else None,
        "forecast_peak_status": status(peak_value),
        "source": current["data_source"] if current else None,
        "retrieved_at": current["retrieval_timestamp"] if current else None,
        "warning_m3s": risk_engine.DISCHARGE_WARNING_M3S,
        "alarm_m3s": risk_engine.DISCHARGE_ALARM_M3S,
    }


async def _flood_history(db: aiosqlite.Connection, province: str) -> Dict[str, Any]:
    cursor = await db.execute(
        """
        SELECT COUNT(*) AS n FROM flood_events WHERE province LIKE ?
        """,
        (f"%{province}%",),
    )
    count_row = await cursor.fetchone()

    cursor = await db.execute(
        """
        SELECT event_date, affected_people
        FROM flood_events
        WHERE province LIKE ?
        ORDER BY event_date DESC
        LIMIT 1
        """,
        (f"%{province}%",),
    )
    last = await cursor.fetchone()

    return {
        "recorded_events": int(count_row["n"]) if count_row else 0,
        "last_event_date": last["event_date"] if last else None,
        "last_event_affected_people": int(last["affected_people"] or 0) if last else None,
    }


async def _basin_summary(
    db: aiosqlite.Connection, provinces: List[Dict[str, Any]]
) -> Dict[str, Any]:
    from app.routers.hydrology import _freshness, _station_status

    cursor = await db.execute(
        "SELECT id, alarm_level, flood_level FROM stations WHERE is_active = 1"
    )
    stations = await cursor.fetchall()

    in_alarm = in_flood = 0
    live_stations = 0
    newest_reading: Optional[str] = None

    for st in stations:
        r_cursor = await db.execute(
            """
            SELECT value, timestamp, data_source FROM water_levels
            WHERE station_id = ? ORDER BY timestamp DESC LIMIT 1
            """,
            (st["id"],),
        )
        reading = await r_cursor.fetchone()
        if not reading:
            continue
        freshness, _ = _freshness(reading["data_source"], reading["timestamp"])
        if freshness not in ("live", "delayed"):
            continue
        live_stations += 1
        if newest_reading is None or reading["timestamp"] > newest_reading:
            newest_reading = reading["timestamp"]
        status = _station_status(float(reading["value"]), st["alarm_level"], st["flood_level"])
        if status == "CRITICAL_FLOOD":
            in_flood += 1
        elif status == "WARNING":
            in_alarm += 1

    cursor = await db.execute(
        """
        SELECT acquisition_date FROM satellite_acquisitions
        WHERE COALESCE(collection, '') != 'admin_upload'
        ORDER BY acquisition_date DESC LIMIT 1
        """
    )
    last_pass = await cursor.fetchone()

    cursor = await db.execute(
        """
        SELECT acquisition_date, water_extent_km2 FROM satellite_acquisitions
        WHERE processed = 1 AND water_extent_km2 IS NOT NULL
        ORDER BY acquisition_date DESC LIMIT 1
        """
    )
    last_extent = await cursor.fetchone()

    cursor = await db.execute(
        "SELECT COUNT(*) AS n FROM alerts WHERE LOWER(status) IN ('active', 'acknowledged')"
    )
    alert_row = await cursor.fetchone()

    return {
        "live_gauges": live_stations,
        "gauges_in_alarm": in_alarm,
        "gauges_in_flood": in_flood,
        "newest_gauge_reading": newest_reading,
        "open_alerts": int(alert_row["n"]) if alert_row else 0,
        "provinces_total": len(provinces),
        "provinces_at_alert_or_above": sum(1 for p in provinces if p["action"]["index"] >= 2),
        "satellite": {
            "last_pass": last_pass["acquisition_date"] if last_pass else None,
            "last_processed_pass": last_extent["acquisition_date"] if last_extent else None,
            "last_water_extent_km2": (
                float(last_extent["water_extent_km2"]) if last_extent else None
            ),
        },
    }


# ---------------------------------------------------------------------
# Action level + safe-site posture
# ---------------------------------------------------------------------

def _derive_action(
    risk_index: int,
    gauges: List[Dict[str, Any]],
    alerts: List[Dict[str, Any]],
) -> Dict[str, Any]:
    gauge_index = -1
    for g in gauges:
        if not g["counts_for_risk"]:
            continue
        if g["status"] == "CRITICAL_FLOOD":
            gauge_index = max(gauge_index, 3)
        elif g["status"] == "WARNING":
            gauge_index = max(gauge_index, 2)

    alert_index = max((level_index(a["severity"]) for a in alerts), default=-1)

    index = max(risk_index, gauge_index, alert_index, 0)

    driven_by: List[Dict[str, Any]] = []
    if risk_index >= 0:
        driven_by.append({"source": "risk_model", "level": LEVEL_CATEGORIES[risk_index]})
    if gauge_index >= 0:
        driven_by.append({"source": "gauge", "level": LEVEL_CATEGORIES[gauge_index]})
    if alert_index >= 0:
        driven_by.append({"source": "alert", "level": LEVEL_CATEGORIES[alert_index]})

    action = ACTIONS[index]
    return {
        "index": index,
        "level": LEVEL_KEYS[index],
        "category": LEVEL_CATEGORIES[index],
        "code": action["code"],
        "label_en": action["label_en"],
        "label_km": action["label_km"],
        "guidance_en": action["guidance_en"],
        "driven_by": driven_by,
        "escalated": index > max(risk_index, 0),
    }


def _site_status(site: Dict[str, Any], action_index: int) -> Dict[str, Any]:
    group = _site_group(site["type"])
    return {
        "name": site["name"],
        "name_km": site["name_km"],
        "type": site["type"],
        "group": group,
        "capacity_people": site.get("capacity_people"),
        "elevation_m": site["elevation_m"],
        "lat": site["lat"],
        "lon": site["lon"],
        "posture": SITE_POSTURES[group][action_index],
    }


# ---------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------

async def resolve_location(db: aiosqlite.Connection, key: str):
    """Find a monitoring location from 'pursat', 'kampong-chhnang', 'Kampong Chhnang' or an id."""
    cleaned = key.strip().replace("-", " ").replace("_", " ")
    cursor = await db.execute(
        """
        SELECT id, name, name_km, province, elevation_m, distance_to_lake_km,
               flood_frequency_score
        FROM monitoring_locations
        WHERE LOWER(name) = LOWER(?) OR LOWER(province) = LOWER(?) OR id = ?
        LIMIT 1
        """,
        (cleaned, cleaned, int(key) if key.isdigit() else -1),
    )
    return await cursor.fetchone()


async def build_province_risk(
    db: aiosqlite.Connection,
    loc: aiosqlite.Row,
    metrics: Dict[str, Any],
    now: datetime,
) -> Dict[str, Any]:
    location_id = int(loc["id"])
    key = loc["name"].lower().replace(" ", "_")
    info = metrics.get(key, {})

    # ---- risk model ------------------------------------------------
    assessment = await _latest_assessment(db, location_id)
    risk: Dict[str, Any]
    risk_index = -1

    if assessment is None:
        risk = {
            "available": False,
            "category": None,
            "level": None,
            "score": None,
            "freshness": "none",
            "data_status": "no_assessment",
            "factors": [],
        }
    else:
        confidence = _safe_json(assessment["confidence_info_json"])
        factors_raw = _safe_json(assessment["contributing_factors_json"])
        assessed_at = _parse_dt(assessment["assessment_date"])
        age_minutes = (
            round((now - assessed_at).total_seconds() / 60.0, 1) if assessed_at else None
        )

        if age_minutes is None:
            freshness = "none"
        elif age_minutes <= ASSESSMENT_FRESH_MINUTES:
            freshness = "fresh"
        elif age_minutes <= ASSESSMENT_DELAYED_MINUTES:
            freshness = "delayed"
        else:
            freshness = "stale"

        risk_index = level_index(assessment["risk_category"])
        factors = []
        for name, detail in factors_raw.items():
            if not isinstance(detail, dict):
                continue
            factors.append(
                {
                    "name": name,
                    "label": FACTOR_LABELS.get(name, name.title()),
                    "score": detail.get("score"),
                    "weight": detail.get("weight"),
                    "contribution": detail.get("weighted_contribution"),
                }
            )
        factors.sort(key=lambda f: f["contribution"] or 0, reverse=True)

        risk = {
            "available": True,
            "category": assessment["risk_category"],
            "level": LEVEL_KEYS[risk_index] if risk_index >= 0 else None,
            "score": round(float(assessment["risk_probability"]), 1),
            "primary_driver": confidence.get("primary_driver"),
            "assessment_date": assessment["assessment_date"],
            "age_minutes": age_minutes,
            "freshness": freshness,
            "data_status": confidence.get("data_status"),
            "data_coverage_percent": confidence.get("data_coverage_percent"),
            "explanation_en": confidence.get("explanation_en", ""),
            "explanation_km": confidence.get("explanation_km", ""),
            "model_version": assessment["model_version"],
            "factors": factors,
        }

    # ---- other live sources ---------------------------------------
    trend = await _risk_history(db, location_id, now)
    gauges = await _province_gauges(db, loc["province"])
    alerts = await _province_alerts(db, loc["province"])
    discharge = await _discharge(db, location_id, now)
    history = await _flood_history(db, loc["province"])

    action = _derive_action(risk_index, gauges, alerts)
    sites = [_site_status(s, action["index"]) for s in info.get("infrastructure", [])]

    return {
        "location_id": location_id,
        "key": slugify(loc["name"]),
        "name": loc["name"],
        "name_km": loc["name_km"] or loc["name"],
        "province": loc["province"],
        "province_code": info.get("code"),
        "population": info.get("population"),
        "vulnerable_communes": info.get("vulnerable_communes"),
        "elevation_m": loc["elevation_m"],
        "risk": risk,
        "trend": trend,
        "action": action,
        "gauges": gauges,
        "alerts": alerts,
        "discharge": discharge,
        "safe_sites": sites,
        "shelter_capacity_people": sum(
            s["capacity_people"] or 0 for s in sites if s["group"] == "shelter"
        ),
        "flood_history": history,
    }


async def build_community_risk(
    db: aiosqlite.Connection, metrics: Dict[str, Any]
) -> Dict[str, Any]:
    now = datetime.now(timezone.utc)

    cursor = await db.execute(
        """
        SELECT id, name, name_km, province, elevation_m, distance_to_lake_km,
               flood_frequency_score
        FROM monitoring_locations
        ORDER BY id ASC
        """
    )
    locations = await cursor.fetchall()

    provinces: List[Dict[str, Any]] = []
    for loc in locations:
        try:
            provinces.append(await build_province_risk(db, loc, metrics, now))
        except Exception:
            logger.exception("Community risk failed for location %s", loc["id"])

    return {
        "generated_at": now.isoformat(),
        "model_version": risk_engine.MODEL_VERSION,
        "basin": await _basin_summary(db, provinces),
        "provinces": provinces,
    }