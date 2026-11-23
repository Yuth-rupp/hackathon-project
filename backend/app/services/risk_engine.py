"""
FloodPulse AI - Multi-Factor Flood Risk Assessment Engine

Calculates a 0-100 flood risk score using:
1. Rainfall
2. Hydrology
3. Soil moisture
4. Seasonal conditions
5. Historical flood frequency

This is a weighted rule-based model.
It does not produce calibrated flood probabilities.
"""

import asyncio
import json
import logging
import math
import time
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple

import aiosqlite
import httpx

from app.config import settings
from app.services.realtime import broker

logger = logging.getLogger(__name__)


class RiskEngine:
    """Weighted rule-based flood risk assessment engine."""

    WEIGHT_RAINFALL = 0.25
    WEIGHT_HYDRO = 0.30
    WEIGHT_SOIL = 0.15
    WEIGHT_SEASONAL = 0.15
    WEIGHT_HISTORICAL = 0.15

    WEIGHTS = {
        "rainfall": WEIGHT_RAINFALL,
        "hydrology": WEIGHT_HYDRO,
        "soil": WEIGHT_SOIL,
        "seasonal": WEIGHT_SEASONAL,
        "historical": WEIGHT_HISTORICAL,
    }

    MODEL_VERSION = "v2.1-rule-based"
    MODEL_TYPE = "MultiFactorRuleEngine"

    DISCHARGE_BASELINE_M3S = 800.0
    DISCHARGE_WARNING_M3S = 2500.0
    DISCHARGE_ALARM_M3S = 4000.0

    LOCAL_UTC_OFFSET_HOURS = 7
    WEATHER_HISTORY_DAYS = 30
    WEATHER_HISTORY_REFRESH_MINUTES = 90
    WEATHER_HISTORY_SOURCE = "Open-Meteo history"
    OPEN_METEO_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

    THRESHOLDS = {
        "Low": (0.0, 25.0),
        "Moderate": (25.0, 50.0),
        "High": (50.0, 75.0),
        "Very High": (75.0, 100.0),
    }

    def __init__(self) -> None:
        self._rate_limited_until: float = 0.0

    # ---------------------------------------------------------
    # Utility functions
    # ---------------------------------------------------------

    @staticmethod
    def _clamp(
        value: float,
        minimum: float = 0.0,
        maximum: float = 100.0,
    ) -> float:
        return max(minimum, min(maximum, value))

    @staticmethod
    def _to_float(value: Any) -> Optional[float]:
        if value is None:
            return None

        try:
            number = float(value)
            if not math.isfinite(number):
                return None
            return number
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _parse_datetime(value: Optional[Any]) -> Optional[datetime]:
        if not value:
            return None

        try:
            parsed = datetime.fromisoformat(
                str(value).replace("Z", "+00:00")
            )

            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)

            return parsed.astimezone(timezone.utc)

        except (ValueError, TypeError):
            return None

    @staticmethod
    def _row_value(row: Any, key: str) -> Any:
        if row is None:
            return None

        try:
            return row[key]
        except (KeyError, IndexError, TypeError):
            return None

    @staticmethod
    def _round_or_none(value: Optional[float], digits: int = 2):
        if value is None:
            return None
        return round(value, digits)

    @classmethod
    def _parse_weather_time(cls, value: Optional[Any]) -> Optional[datetime]:
        """
        Parse a weather timestamp into UTC.
        Naive Open-Meteo times are Asia/Bangkok local time, not UTC.
        """
        if not value:
            return None

        try:
            parsed = datetime.fromisoformat(
                str(value).replace("Z", "+00:00")
            )
        except (ValueError, TypeError):
            return None

        if parsed.tzinfo is None:
            parsed = parsed - timedelta(hours=cls.LOCAL_UTC_OFFSET_HOURS)
            return parsed.replace(tzinfo=timezone.utc)

        return parsed.astimezone(timezone.utc)

    async def _ensure_weather_history(
        self,
        db: aiosqlite.Connection,
        location_id: int,
        lat: Optional[float],
        lon: Optional[float],
        now: datetime,
    ) -> None:
        if lat is None or lon is None:
            return

        if time.time() < self._rate_limited_until:
            return

        cursor = await db.execute(
            """
            SELECT MAX(retrieval_timestamp) AS last_fetch
            FROM weather_data
            WHERE location_id = ?
              AND data_source = ?
            """,
            (location_id, self.WEATHER_HISTORY_SOURCE),
        )

        row = await cursor.fetchone()
        last_fetch = self._parse_datetime(
            self._row_value(row, "last_fetch")
        )

        if (
            last_fetch is not None
            and (now - last_fetch)
            < timedelta(minutes=self.WEATHER_HISTORY_REFRESH_MINUTES)
        ):
            return

        params = {
            "latitude": lat,
            "longitude": lon,
            "hourly": "precipitation,soil_moisture_0_to_7cm",
            "past_days": self.WEATHER_HISTORY_DAYS,
            "forecast_days": 1,
            "timezone": "Asia/Bangkok",
        }

        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(25.0, connect=10.0)
            ) as client:
                response = await client.get(
                    self.OPEN_METEO_FORECAST_URL,
                    params=params,
                    headers={"User-Agent": "FloodPulse-AI/1.0"},
                )
                response.raise_for_status()
                payload = response.json()

        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 429:
                self._rate_limited_until = time.time() + 900
                logger.warning(
                    "Open-Meteo rate-limited (429); pausing history sync for 15 minutes."
                )
            else:
                logger.warning(
                    "Could not fetch weather history for location %s: %s: %s",
                    location_id,
                    type(exc).__name__,
                    exc,
                )
            return

        except Exception as exc:
            logger.warning(
                "Could not fetch weather history for location %s: %s: %s",
                location_id,
                type(exc).__name__,
                exc,
            )
            return

        hourly = payload.get("hourly") or {}
        times = hourly.get("time") or []
        precipitation = hourly.get("precipitation") or []
        soil = hourly.get("soil_moisture_0_to_7cm") or []

        if not times:
            logger.warning(
                "Open-Meteo returned no hourly weather for location %s.",
                location_id,
            )
            return

        now_iso = now.isoformat()

        rows = [
            (
                location_id,
                times[index],
                "hourly",
                precipitation[index] if index < len(precipitation) else None,
                soil[index] if index < len(soil) else None,
                self.WEATHER_HISTORY_SOURCE,
                now_iso,
            )
            for index in range(len(times))
        ]

        await db.execute(
            """
            DELETE FROM weather_data
            WHERE location_id = ?
              AND data_source = ?
            """,
            (location_id, self.WEATHER_HISTORY_SOURCE),
        )

        await db.executemany(
            """
            INSERT INTO weather_data (
                location_id, timestamp, data_type,
                precipitation_mm, soil_moisture,
                data_source, retrieval_timestamp
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )

        await db.commit()

        logger.info(
            "Stored %s hourly weather records for location %s.",
            len(rows),
            location_id,
        )

    def _freshness_window_hours(self) -> float:
        try:
            value = float(
                getattr(settings, "GAUGE_STALE_AFTER_HOURS", 48)
            )
            return max(1.0, value)
        except (TypeError, ValueError):
            return 48.0

    # ---------------------------------------------------------
    # Factor calculations
    # ---------------------------------------------------------

    def compute_rainfall_score(
        self,
        rain_3d: float,
        rain_7d: float,
        rain_30d: float,
    ) -> float:
        score_3d = min(max(rain_3d, 0.0) / 150.0, 1.0) * 100
        score_7d = min(max(rain_7d, 0.0) / 250.0, 1.0) * 100
        score_30d = min(max(rain_30d, 0.0) / 500.0, 1.0) * 100

        score = (
            score_3d * 0.50
            + score_7d * 0.30
            + score_30d * 0.20
        )

        return round(self._clamp(score), 2)

    def compute_discharge_score(
        self,
        discharge_m3s: float,
        baseline_m3s: float = DISCHARGE_BASELINE_M3S,
        warning_m3s: float = DISCHARGE_WARNING_M3S,
        alarm_m3s: float = DISCHARGE_ALARM_M3S,
    ) -> float:
        discharge = max(0.0, discharge_m3s)

        if not (
            0 < baseline_m3s < warning_m3s < alarm_m3s
        ):
            raise ValueError("Invalid discharge thresholds.")

        if discharge <= baseline_m3s:
            score = (
                discharge / baseline_m3s
            ) * 25.0

        elif discharge <= warning_m3s:
            score = 25.0 + (
                (discharge - baseline_m3s)
                / (warning_m3s - baseline_m3s)
            ) * 35.0

        elif discharge <= alarm_m3s:
            score = 60.0 + (
                (discharge - warning_m3s)
                / (alarm_m3s - warning_m3s)
            ) * 30.0

        else:
            score = 90.0 + (
                (discharge - alarm_m3s)
                / alarm_m3s
            ) * 10.0

        return round(self._clamp(score), 2)

    def compute_water_level_score(
        self,
        water_level_m: float,
        alarm_level_m: float,
    ) -> float:
        if alarm_level_m <= 0:
            raise ValueError("Alarm level must be greater than zero.")

        ratio = water_level_m / alarm_level_m

        if ratio < 0.70:
            score = (ratio / 0.70) * 30.0
        elif ratio < 0.90:
            score = 30.0 + ((ratio - 0.70) / 0.20) * 40.0
        elif ratio < 1.0:
            score = 70.0 + ((ratio - 0.90) / 0.10) * 20.0
        else:
            score = 90.0 + ((ratio - 1.0) / 0.20) * 10.0

        return round(self._clamp(score), 2)

    def compute_hydro_score(
        self,
        discharge_m3s: Optional[float] = None,
        water_level_m: Optional[float] = None,
        alarm_level_m: Optional[float] = None,
    ) -> Optional[float]:
        scores = []

        if discharge_m3s is not None:
            scores.append(
                self.compute_discharge_score(discharge_m3s)
            )

        if (
            water_level_m is not None
            and alarm_level_m is not None
            and alarm_level_m > 0
        ):
            scores.append(
                self.compute_water_level_score(
                    water_level_m,
                    alarm_level_m,
                )
            )

        if not scores:
            return None

        return round(sum(scores) / len(scores), 2)

    def compute_soil_score(
        self,
        soil_moisture_m3m3: float,
    ) -> float:
        moisture = self._clamp(soil_moisture_m3m3, 0.0, 1.0)

        if moisture <= 0.15:
            score = (moisture / 0.15) * 15.0
        elif moisture <= 0.35:
            score = 15.0 + (
                (moisture - 0.15) / 0.20
            ) * 45.0
        else:
            score = 60.0 + (
                (moisture - 0.35) / 0.13
            ) * 40.0

        return round(self._clamp(score), 2)

    def compute_seasonal_factor(
        self,
        dt: Optional[datetime] = None,
    ) -> float:
        if dt is None:
            dt = datetime.now(timezone.utc)

        day = dt.timetuple().tm_yday

        if 120 <= day <= 300:
            normalized = (day - 120) / 180.0
            score = 20.0 + 80.0 * math.sin(
                normalized * math.pi * 0.95
            )

        elif day > 300:
            decay = (day - 300) / 65.0
            score = max(
                10.0,
                80.0 * math.exp(-decay * 2.0),
            )

        else:
            score = max(
                5.0,
                15.0 - (day / 120.0) * 10.0,
            )

        return round(self._clamp(score), 2)

    def normalize_historical_score(
        self,
        historical_value: float,
    ) -> float:
        value = max(0.0, historical_value)

        if value <= 1.0:
            value *= 100.0

        return round(self._clamp(value), 2)

    def classify_category(self, score: float) -> str:
        if score < 25:
            return "Low"
        if score < 50:
            return "Moderate"
        if score < 75:
            return "High"
        return "Very High"

    # ---------------------------------------------------------
    # Weighted score and factor helpers
    # ---------------------------------------------------------

    def _add_factor(
        self,
        factors: Dict[str, Any],
        factor_scores: Dict[str, float],
        name: str,
        score: float,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        weight = self.WEIGHTS[name]
        weighted_contribution = round(score * weight, 2)

        factor_scores[name] = round(self._clamp(score), 2)

        factors[name] = {
            "score": factor_scores[name],
            "weight": weight,
            "weighted_contribution": weighted_contribution,
            **(details or {}),
        }

    def _calculate_weighted_risk(
        self,
        factor_scores: Dict[str, float],
    ) -> Tuple[float, float]:
        available_weight = sum(
            self.WEIGHTS[name]
            for name in factor_scores
        )

        if available_weight <= 0:
            raise ValueError("No usable risk factor data is available.")

        weighted_total = sum(
            score * self.WEIGHTS[name]
            for name, score in factor_scores.items()
        )

        risk_score = self._clamp(
            weighted_total / available_weight
        )

        coverage_percent = available_weight * 100.0

        return round(risk_score, 1), round(coverage_percent, 1)

    # ---------------------------------------------------------
    # Explanations
    # ---------------------------------------------------------

    def generate_explanations(
        self,
        category: str,
        risk_score: float,
        factors: Dict[str, Any],
        location_name: str,
        province: str,
    ) -> Tuple[str, str]:
        reasons = []

        rainfall = factors.get("rainfall", {})
        hydrology = factors.get("hydrology", {})
        soil = factors.get("soil", {})
        seasonal = factors.get("seasonal", {})
        historical = factors.get("historical", {})

        if rainfall.get("score", 0) >= 50:
            rain_7d = rainfall.get("rain_7d_mm")
            if rain_7d is not None:
                reasons.append(
                    f"elevated rainfall ({rain_7d:.1f} mm in 7 days)"
                )
            else:
                reasons.append("elevated rainfall")

        if hydrology.get("score", 0) >= 50:
            reasons.append("elevated river or water-level conditions")

        if soil.get("score", 0) >= 60:
            reasons.append("high soil moisture")

        if seasonal.get("score", 0) >= 70:
            reasons.append("seasonal flood-pulse conditions")

        if historical.get("score", 0) >= 60:
            reasons.append("higher historical flood frequency")

        if not reasons:
            reasons.append("no high-scoring measured physical factor")

        explanation = (
            f"{category.upper()} FLOOD RISK in {location_name}, "
            f"{province}. The calculated risk score is "
            f"{risk_score:.1f}/100. Main contributing conditions: "
            f"{', '.join(reasons)}."
        )

        if "hydrology" not in factors:
            explanation += (
                " Current hydrological observations were unavailable "
                "or stale and were excluded from the score."
            )

        return explanation, ""

    # ---------------------------------------------------------
    # Database assessment
    # ---------------------------------------------------------

    async def assess_location(
        self,
        location_id: int,
        db: aiosqlite.Connection,
        prediction_horizon_days: int = 7,
    ) -> Dict[str, Any]:

        if not 1 <= prediction_horizon_days <= 14:
            raise ValueError(
                "Prediction horizon must be between 1 and 14 days."
            )

        now = datetime.now(timezone.utc)
        now_iso = now.isoformat()

        cursor = await db.execute(
            """
            SELECT
                id,
                name,
                name_km,
                province,
                flood_frequency_score,
                lat,
                lon
            FROM monitoring_locations
            WHERE id = ?
            """,
            (location_id,),
        )

        location = await cursor.fetchone()

        if location is None:
            raise ValueError(
                f"Monitoring location {location_id} was not found."
            )

        await self._ensure_weather_history(
            db=db,
            location_id=location_id,
            lat=self._to_float(self._row_value(location, "lat")),
            lon=self._to_float(self._row_value(location, "lon")),
            now=now,
        )

        local_now = now + timedelta(hours=self.LOCAL_UTC_OFFSET_HOURS)

        def local_text(moment: datetime) -> str:
            return moment.strftime("%Y-%m-%dT%H:%M")

        local_now_text = local_text(local_now)
        local_3d_text = local_text(local_now - timedelta(days=3))
        local_7d_text = local_text(local_now - timedelta(days=7))
        local_30d_text = local_text(local_now - timedelta(days=30))

        weather_cursor = await db.execute(
            """
            SELECT
                COALESCE(SUM(CASE WHEN timestamp >= :t3
                    THEN COALESCE(precipitation_mm, 0) ELSE 0 END), 0)
                    AS rain_3d,
                COALESCE(SUM(CASE WHEN timestamp >= :t7
                    THEN COALESCE(precipitation_mm, 0) ELSE 0 END), 0)
                    AS rain_7d,
                COALESCE(SUM(COALESCE(precipitation_mm, 0)), 0)
                    AS rain_30d,
                AVG(CASE WHEN timestamp >= :t3
                    THEN soil_moisture END) AS avg_soil_moisture,
                MAX(timestamp) AS latest_weather_timestamp,
                COUNT(*) AS record_count
            FROM weather_data
            WHERE id IN (
                SELECT MAX(id)
                FROM weather_data
                WHERE location_id = :location_id
                  AND COALESCE(data_type, '') != 'current'
                  AND timestamp >= :t30
                  AND timestamp <= :now
                GROUP BY timestamp
            )
            """,
            {
                "t3": local_3d_text,
                "t7": local_7d_text,
                "t30": local_30d_text,
                "now": local_now_text,
                "location_id": location_id,
            },
        )

        weather_row = await weather_cursor.fetchone()

        record_count = int(
            self._row_value(weather_row, "record_count") or 0
        )

        if record_count > 0:
            rain_3d = self._to_float(
                self._row_value(weather_row, "rain_3d")
            )
            rain_7d = self._to_float(
                self._row_value(weather_row, "rain_7d")
            )
            rain_30d = self._to_float(
                self._row_value(weather_row, "rain_30d")
            )
            soil_moisture = self._to_float(
                self._row_value(weather_row, "avg_soil_moisture")
            )
        else:
            rain_3d = rain_7d = rain_30d = soil_moisture = None

        weather_timestamp = self._row_value(
            weather_row,
            "latest_weather_timestamp",
        )

        weather_datetime = self._parse_weather_time(weather_timestamp)
        weather_age_minutes = None
        weather_is_fresh = False

        if weather_datetime is not None:
            weather_age_minutes = max(
                0.0,
                (now - weather_datetime).total_seconds() / 60.0,
            )
            weather_is_fresh = weather_age_minutes <= 48 * 60

        factors: Dict[str, Any] = {}
        factor_scores: Dict[str, float] = {}

        if (
            weather_is_fresh
            and rain_3d is not None
            and rain_7d is not None
            and rain_30d is not None
        ):
            rainfall_score = self.compute_rainfall_score(
                rain_3d,
                rain_7d,
                rain_30d,
            )

            self._add_factor(
                factors,
                factor_scores,
                "rainfall",
                rainfall_score,
                {
                    "rain_3d_mm": round(rain_3d, 2),
                    "rain_7d_mm": round(rain_7d, 2),
                    "rain_30d_mm": round(rain_30d, 2),
                },
            )

        if (
            weather_is_fresh
            and soil_moisture is not None
            and 0 <= soil_moisture <= 1
        ):
            soil_score = self.compute_soil_score(soil_moisture)

            self._add_factor(
                factors,
                factor_scores,
                "soil",
                soil_score,
                {
                    "soil_moisture_vol": round(soil_moisture, 3),
                },
            )

        discharge_cursor = await db.execute(
            """
            SELECT discharge_m3s, date
            FROM river_discharge
            WHERE location_id = ?
              AND discharge_m3s IS NOT NULL
              AND date <= ?
            ORDER BY date DESC
            LIMIT 1
            """,
            (location_id, now.strftime("%Y-%m-%d")),
        )

        discharge_row = await discharge_cursor.fetchone()

        discharge = self._to_float(
            self._row_value(discharge_row, "discharge_m3s")
        )
        discharge_date = self._row_value(discharge_row, "date")
        discharge_datetime = self._parse_datetime(discharge_date)

        discharge_age_minutes = None
        discharge_is_fresh = False

        if discharge_datetime is not None:
            discharge_age_minutes = max(
                0.0,
                (now - discharge_datetime).total_seconds() / 60.0,
            )
            discharge_is_fresh = discharge_age_minutes <= 48 * 60

        station_cursor = await db.execute(
            """
            SELECT
                wl.value,
                wl.timestamp,
                s.alarm_level,
                s.flood_level
            FROM water_levels wl
            INNER JOIN stations s
                ON wl.station_id = s.id
            WHERE s.province LIKE ?
              AND s.is_active = 1
              AND wl.value IS NOT NULL
            ORDER BY wl.timestamp DESC
            LIMIT 1
            """,
            (f"%{location['province']}%",),
        )

        station_row = await station_cursor.fetchone()

        water_level = self._to_float(
            self._row_value(station_row, "value")
        )
        alarm_level = self._to_float(
            self._row_value(station_row, "alarm_level")
        )
        water_timestamp = self._row_value(
            station_row,
            "timestamp",
        )

        water_datetime = self._parse_datetime(water_timestamp)
        water_age_minutes = None
        water_is_fresh = False

        if water_datetime is not None:
            water_age_minutes = max(
                0.0,
                (now - water_datetime).total_seconds() / 60.0,
            )
            water_is_fresh = (
                water_age_minutes
                <= self._freshness_window_hours() * 60
            )

        usable_discharge = (
            discharge if discharge_is_fresh else None
        )

        usable_water_level = (
            water_level
            if water_is_fresh and alarm_level is not None
            else None
        )

        usable_alarm_level = (
            alarm_level if usable_water_level is not None else None
        )

        hydro_score = self.compute_hydro_score(
            discharge_m3s=usable_discharge,
            water_level_m=usable_water_level,
            alarm_level_m=usable_alarm_level,
        )

        if hydro_score is not None:
            self._add_factor(
                factors,
                factor_scores,
                "hydrology",
                hydro_score,
                {
                    "discharge_m3s": usable_discharge,
                    "water_level_m": usable_water_level,
                    "alarm_level_m": usable_alarm_level,
                    "discharge_score": (
                        self.compute_discharge_score(usable_discharge)
                        if usable_discharge is not None
                        else None
                    ),
                    "water_level_score": (
                        self.compute_water_level_score(
                            usable_water_level,
                            usable_alarm_level,
                        )
                        if (
                            usable_water_level is not None
                            and usable_alarm_level is not None
                        )
                        else None
                    ),
                    "source_status": "available",
                },
            )

        seasonal_score = self.compute_seasonal_factor(now)

        self._add_factor(
            factors,
            factor_scores,
            "seasonal",
            seasonal_score,
            {
                "day_of_year": now.timetuple().tm_yday,
            },
        )

        historical_value = self._to_float(
            self._row_value(location, "flood_frequency_score")
        )

        if historical_value is not None:
            historical_score = self.normalize_historical_score(
                historical_value
            )

            self._add_factor(
                factors,
                factor_scores,
                "historical",
                historical_score,
                {
                    "source_value": historical_value,
                },
            )

        risk_score, coverage_percent = self._calculate_weighted_risk(
            factor_scores
        )

        category = self.classify_category(risk_score)

        primary_driver = (
            max(
                factors.items(),
                key=lambda item: item[1]["weighted_contribution"],
            )[0]
            if factors
            else "Not available"
        )

        data_freshness = {
            "weather_timestamp": weather_timestamp,
            "weather_age_minutes": self._round_or_none(
                weather_age_minutes, 1
            ),
            "weather_fresh": weather_is_fresh,
            "discharge_timestamp": discharge_date,
            "discharge_age_minutes": self._round_or_none(
                discharge_age_minutes, 1
            ),
            "discharge_fresh": discharge_is_fresh,
            "water_level_timestamp": water_timestamp,
            "water_level_age_minutes": self._round_or_none(
                water_age_minutes, 1
            ),
            "water_level_fresh": water_is_fresh,
        }

        if coverage_percent >= 85:
            data_status = "good"
        elif coverage_percent >= 60:
            data_status = "partial"
        else:
            data_status = "limited"

        explanation_en, explanation_km = self.generate_explanations(
            category=category,
            risk_score=risk_score,
            factors=factors,
            location_name=location["name"],
            province=location["province"],
        )

        assessment_record = {
            "location_id": location_id,
            "location_name": location["name"],
            "location_name_km": location["name_km"],
            "province": location["province"],
            "assessment_date": now_iso,
            "prediction_horizon_days": prediction_horizon_days,
            "risk_probability": risk_score,
            "risk_score": risk_score,
            "risk_category": category,
            "primary_driver": primary_driver,
            "model_version": self.MODEL_VERSION,
            "model_type": self.MODEL_TYPE,
            "contributing_factors": factors,
            "data_coverage_percent": coverage_percent,
            "data_status": data_status,
            "data_freshness": data_freshness,
            "explanation_en": explanation_en,
            "explanation_km": explanation_km,
        }

        confidence_info = {
            "explanation_en": explanation_en,
            "explanation_km": explanation_km,
            "data_coverage_percent": coverage_percent,
            "data_status": data_status,
            "data_freshness": data_freshness,
            "primary_driver": primary_driver,
        }

        await db.execute(
            """
            INSERT INTO risk_assessments (
                location_id,
                assessment_date,
                prediction_horizon_days,
                risk_probability,
                risk_category,
                model_version,
                model_type,
                contributing_factors_json,
                confidence_info_json,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                location_id,
                now_iso,
                prediction_horizon_days,
                risk_score,
                category,
                self.MODEL_VERSION,
                self.MODEL_TYPE,
                json.dumps(factors),
                json.dumps(confidence_info),
                now_iso,
            ),
        )

        await db.commit()

        try:
            broker.publish(
                "risk_updated",
                {
                    "location_id": location_id,
                    "location_name": location["name"],
                    "province": location["province"],
                    "risk_category": category,
                    "risk_score": risk_score,
                    "assessment_date": now_iso,
                },
            )
        except Exception:
            logger.exception("Could not publish risk_updated event.")

        return assessment_record

    # ---------------------------------------------------------
    # Assess all monitoring locations
    # ---------------------------------------------------------

    async def assess_all_locations(
        self,
        db: aiosqlite.Connection,
    ) -> List[Dict[str, Any]]:
        cursor = await db.execute(
            """
            SELECT id
            FROM monitoring_locations
            ORDER BY id ASC
            """
        )

        locations = await cursor.fetchall()
        results: List[Dict[str, Any]] = []

        for index, row in enumerate(locations):
            location_id = int(row["id"])

            try:
                result = await self.assess_location(
                    location_id=location_id,
                    db=db,
                )
                results.append(result)

            except Exception:
                logger.exception(
                    "Risk assessment failed for location %s",
                    location_id,
                )

            if index < len(locations) - 1:
                await asyncio.sleep(1.5)

        return results


risk_engine = RiskEngine()