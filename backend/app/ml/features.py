"""
FloodPulse AI - Hydrometeorological Feature Engineering Pipeline
Extracts, transforms, and normalizes predictive features from telemetry and historical archives.
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Tuple

import aiosqlite
import numpy as np

logger = logging.getLogger(__name__)

FEATURE_NAMES = [
    "rainfall_3d",
    "rainfall_7d",
    "rainfall_30d",
    "discharge_current",
    "discharge_max",
    "discharge_trend_3d",
    "soil_moisture_avg",
    "month",
    "is_monsoon_season",
    "flood_frequency_historical",
    "days_since_last_flood"
]


async def extract_features(
    location_id: int,
    reference_date: Optional[datetime] = None,
    db: Optional[aiosqlite.Connection] = None
) -> Dict[str, Any]:
    """
    Extract 11 core machine learning features for flood risk prediction at a specific location and date:
    1. rainfall_3d: 3-day cumulative precipitation (mm)
    2. rainfall_7d: 7-day cumulative precipitation (mm)
    3. rainfall_30d: 30-day cumulative precipitation (mm)
    4. discharge_current: Latest river discharge (m³/s)
    5. discharge_max: Maximum discharge over previous 7 days (m³/s)
    6. discharge_trend_3d: Rate of change in discharge over past 3 days (m³/s per day)
    7. soil_moisture_avg: Average volumetric soil moisture content
    8. month: Calendar month (1-12)
    9. is_monsoon_season: Binary flag (1 if June - October, else 0)
    10. flood_frequency_historical: Historical vulnerability factor (0.0 - 1.0)
    11. days_since_last_flood: Elapsed days since previous recorded disaster event
    """
    if reference_date is None:
        ref_dt = datetime.now(timezone.utc)
    else:
        ref_dt = reference_date

    ref_iso = ref_dt.isoformat()
    dt_3d = (ref_dt - timedelta(days=3)).isoformat()
    dt_7d = (ref_dt - timedelta(days=7)).isoformat()
    dt_30d = (ref_dt - timedelta(days=30)).isoformat()

    # 1. Location details & historical baseline
    loc_cursor = await db.execute(
        "SELECT id, name, province, flood_frequency_score FROM monitoring_locations WHERE id = ?",
        (location_id,)
    )
    loc = await loc_cursor.fetchone()
    flood_freq = float(loc["flood_frequency_score"]) if loc and loc["flood_frequency_score"] is not None else 0.65
    province = loc["province"] if loc else ""

    # 2. Weather rainfall accumulation & soil moisture
    w_cursor = await db.execute(
        """
        SELECT 
            COALESCE(SUM(CASE WHEN timestamp >= ? THEN precipitation_mm ELSE 0 END), 0.0) as rain_3d,
            COALESCE(SUM(CASE WHEN timestamp >= ? THEN precipitation_mm ELSE 0 END), 0.0) as rain_7d,
            COALESCE(SUM(precipitation_mm), 0.0) as rain_30d,
            AVG(soil_moisture) as avg_soil
        FROM weather_data 
        WHERE location_id = ? AND timestamp <= ? AND timestamp >= ?
        """,
        (dt_3d, dt_7d, location_id, ref_iso, dt_30d)
    )
    w_row = await w_cursor.fetchone()
    rainfall_3d = float(w_row["rain_3d"]) if w_row and w_row["rain_3d"] is not None else 0.0
    rainfall_7d = float(w_row["rain_7d"]) if w_row and w_row["rain_7d"] is not None else 0.0
    rainfall_30d = float(w_row["rain_30d"]) if w_row and w_row["rain_30d"] is not None else 0.0
    soil_moisture_avg = float(w_row["avg_soil"]) if w_row and w_row["avg_soil"] is not None else 0.32

    # 3. River discharge telemetry (current, 7-day max, 3-day trend)
    d_curr_cursor = await db.execute(
        """
        SELECT discharge_m3s, discharge_max, date 
        FROM river_discharge 
        WHERE location_id = ? AND date <= ?
        ORDER BY date DESC LIMIT 1
        """,
        (location_id, ref_iso[:10])
    )
    d_curr_row = await d_curr_cursor.fetchone()
    discharge_current = float(d_curr_row["discharge_m3s"]) if d_curr_row and d_curr_row["discharge_m3s"] is not None else 850.0

    d_7d_cursor = await db.execute(
        """
        SELECT MAX(COALESCE(discharge_max, discharge_m3s)) as max_d 
        FROM river_discharge 
        WHERE location_id = ? AND date <= ? AND date >= ?
        """,
        (location_id, ref_iso[:10], dt_7d[:10])
    )
    d_7d_row = await d_7d_cursor.fetchone()
    discharge_max = float(d_7d_row["max_d"]) if d_7d_row and d_7d_row["max_d"] is not None else discharge_current

    # 3-day past discharge for trend computation
    d_past_cursor = await db.execute(
        """
        SELECT discharge_m3s 
        FROM river_discharge 
        WHERE location_id = ? AND date <= ?
        ORDER BY date DESC LIMIT 1
        """,
        (location_id, dt_3d[:10])
    )
    d_past_row = await d_past_cursor.fetchone()
    discharge_past_3d = float(d_past_row["discharge_m3s"]) if d_past_row and d_past_row["discharge_m3s"] is not None else discharge_current
    discharge_trend_3d = round((discharge_current - discharge_past_3d) / 3.0, 2)

    # 4. Temporal & Seasonal Features
    month = ref_dt.month
    # Tonle Sap monsoon expansion is June (6) through October (10)
    is_monsoon_season = 1 if (6 <= month <= 10) else 0

    # 5. Elapsed time since last recorded flood event in this province
    event_cursor = await db.execute(
        """
        SELECT event_date FROM flood_events 
        WHERE province LIKE ? AND event_date <= ?
        ORDER BY event_date DESC LIMIT 1
        """,
        (f"%{province}%", ref_iso[:10])
    )
    event_row = await event_cursor.fetchone()
    if event_row and event_row["event_date"]:
        try:
            last_date = datetime.fromisoformat(event_row["event_date"].replace("Z", "+00:00"))
            days_since_last_flood = max(0, (ref_dt - last_date).days)
        except Exception:
            days_since_last_flood = 365
    else:
        days_since_last_flood = 730  # Baseline 2 years if no prior event in archive

    features = {
        "rainfall_3d": round(rainfall_3d, 2),
        "rainfall_7d": round(rainfall_7d, 2),
        "rainfall_30d": round(rainfall_30d, 2),
        "discharge_current": round(discharge_current, 1),
        "discharge_max": round(discharge_max, 1),
        "discharge_trend_3d": round(discharge_trend_3d, 1),
        "soil_moisture_avg": round(soil_moisture_avg, 3),
        "month": month,
        "is_monsoon_season": is_monsoon_season,
        "flood_frequency_historical": round(flood_freq, 2),
        "days_since_last_flood": days_since_last_flood,
    }

    return features


def features_to_vector(features: Dict[str, Any]) -> np.ndarray:
    """
    Convert feature dictionary into an ordered 1D numpy vector for ML model inference.
    """
    return np.array([
        features.get(f, 0.0) for f in FEATURE_NAMES
    ], dtype=np.float32)
