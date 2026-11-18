"""
FloodPulse AI - Rule-Based Flood Risk Assessment Engine
Hydrological and meteorological risk modeling specifically calibrated for the Tonle Sap Basin.
"""

import json
import logging
import math
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List, Tuple

import aiosqlite
from app.config import settings

logger = logging.getLogger(__name__)


class RiskEngine:
    """
    Evaluates multi-factor flood vulnerability for Tonle Sap monitoring locations:
    1. Rainfall Score (3d, 7d, 30d cumulative antecedent precipitation) [Weight: 0.25]
    2. Hydrological Score (River discharge and water level vs alarm thresholds) [Weight: 0.30]
    3. Soil Moisture Score (Topsoil and root zone saturation percentage) [Weight: 0.15]
    4. Seasonal Monsoon Score (Tonle Sap pulse curve peak Jun-Oct) [Weight: 0.15]
    5. Historical Vulnerability Score (Historical flood recurrence and disaster frequency) [Weight: 0.15]
    """

    # Calibrated risk weights
    WEIGHT_RAINFALL = 0.25
    WEIGHT_HYDRO = 0.30
    WEIGHT_SOIL = 0.15
    WEIGHT_SEASONAL = 0.15
    WEIGHT_HISTORICAL = 0.15

    # Thresholds for categorical risk classification
    THRESHOLDS = {
        "Low": (0.0, 25.0),
        "Moderate": (25.0, 50.0),
        "High": (50.0, 75.0),
        "Very High": (75.0, 100.0),
    }

    def compute_seasonal_factor(self, dt: Optional[datetime] = None) -> float:
        """
        Calculate Tonle Sap monsoon expansion factor (0 - 100).
        The Mekong flood pulse forces reverse flow into the Tonle Sap lake starting in June,
        peaking in late September/October, and draining back out in November/December.
        Dry season (Jan-Apr): baseline ~5-15.
        Wet season (Jun-Oct): rises to 70-100.
        """
        if dt is None:
            dt = datetime.now(timezone.utc)
        
        # Day of year (1-365)
        day_of_year = dt.timetuple().tm_yday
        # Peak of Tonle Sap lake water level is typically around Day 275 (Early October)
        # Low water level is around Day 110 (Mid April)
        peak_day = 275.0
        
        # Asymmetric seasonal curve modeling the Mekong reverse flow pulse
        # Rise is steep (June-Sept), recession is gradual (Oct-Jan)
        if 120 <= day_of_year <= 300:
            # Monsoon expansion phase
            normalized = (day_of_year - 120) / (300 - 120)
            score = 20.0 + 80.0 * math.sin(normalized * math.pi * 0.95)
        elif day_of_year > 300:
            # Post-monsoon recession phase
            decay = (day_of_year - 300) / (365 - 300)
            score = max(10.0, 80.0 * math.exp(-decay * 2.0))
        else:
            # Low water dry season (Jan - April)
            score = max(5.0, 15.0 - (day_of_year / 120.0) * 10.0)

        return round(float(min(max(score, 0.0), 100.0)), 2)

    def compute_rainfall_score(
        self,
        rain_3d: float,
        rain_7d: float,
        rain_30d: float
    ) -> float:
        """
        Compute rainfall vulnerability score (0 - 100):
        - 3-day rainfall: Flash flood and immediate surface runoff potential (Weight 0.50)
        - 7-day rainfall: Catchment saturation and tributary swell (Weight 0.30)
        - 30-day rainfall: Antecedent Precipitation Index (API) baseline (Weight 0.20)
        """
        # 3-day: 0 to 150mm scale (150mm+ in 3 days is extreme tropical monsoon storm)
        score_3d = min(rain_3d / 150.0, 1.0) * 100.0

        # 7-day: 0 to 250mm scale
        score_7d = min(rain_7d / 250.0, 1.0) * 100.0

        # 30-day: 0 to 500mm scale
        score_30d = min(rain_30d / 500.0, 1.0) * 100.0

        composite = (score_3d * 0.50) + (score_7d * 0.30) + (score_30d * 0.20)
        return round(float(min(max(composite, 0.0), 100.0)), 2)

    def compute_hydro_score(
        self,
        discharge_m3s: float,
        baseline_m3s: float = 800.0,
        warning_m3s: float = 2500.0,
        alarm_m3s: float = 4000.0,
        water_level_m: Optional[float] = None,
        alarm_level_m: Optional[float] = None
    ) -> float:
        """
        Compute hydrological discharge and water level stress score (0 - 100).
        """
        # If explicit water level vs alarm level is provided:
        level_score = 0.0
        if water_level_m is not None and alarm_level_m is not None and alarm_level_m > 0:
            ratio = water_level_m / alarm_level_m
            if ratio < 0.70:
                level_score = (ratio / 0.70) * 30.0
            elif ratio < 0.90:
                level_score = 30.0 + ((ratio - 0.70) / 0.20) * 40.0
            elif ratio < 1.0:
                level_score = 70.0 + ((ratio - 0.90) / 0.10) * 20.0
            else:
                level_score = min(90.0 + ((ratio - 1.0) / 0.2) * 10.0, 100.0)

        # Discharge ratio computation
        discharge_score = 0.0
        if discharge_m3s <= baseline_m3s:
            discharge_score = (discharge_m3s / max(baseline_m3s, 1.0)) * 25.0
        elif discharge_m3s <= warning_m3s:
            discharge_score = 25.0 + ((discharge_m3s - baseline_m3s) / (warning_m3s - baseline_m3s)) * 35.0
        elif discharge_m3s <= alarm_m3s:
            discharge_score = 60.0 + ((discharge_m3s - warning_m3s) / (alarm_m3s - warning_m3s)) * 30.0
        else:
            discharge_score = min(90.0 + ((discharge_m3s - alarm_m3s) / alarm_m3s) * 10.0, 100.0)

        if water_level_m is not None and alarm_level_m is not None:
            final_hydro = (discharge_score * 0.50) + (level_score * 0.50)
        else:
            final_hydro = discharge_score

        return round(float(min(max(final_hydro, 0.0), 100.0)), 2)

    def compute_soil_score(self, soil_moisture_m3m3: float) -> float:
        """
        Convert volumetric soil water content (m³/m³) to saturation percentage score.
        For tropical clay-loam floodplain soils:
        - Wilting point: ~0.15 m³/m³ (0 score)
        - Field capacity: ~0.35 m³/m³ (40 score)
        - Complete saturation: >= 0.48 m³/m³ (100 score)
        """
        if soil_moisture_m3m3 <= 0.15:
            score = (soil_moisture_m3m3 / 0.15) * 15.0
        elif soil_moisture_m3m3 <= 0.35:
            score = 15.0 + ((soil_moisture_m3m3 - 0.15) / 0.20) * 45.0
        else:
            score = 60.0 + ((soil_moisture_m3m3 - 0.35) / 0.13) * 40.0

        return round(float(min(max(score, 0.0), 100.0)), 2)

    def classify_category(self, score: float) -> str:
        """Categorize risk score into Low, Moderate, High, or Very High."""
        if score < 25.0:
            return "Low"
        elif score < 50.0:
            return "Moderate"
        elif score < 75.0:
            return "High"
        else:
            return "Very High"

    def generate_explanations(
        self,
        category: str,
        probability: float,
        factors: Dict[str, Any],
        location_name: str,
        province: str
    ) -> Tuple[str, str]:
        """
        Generate comprehensive bilingual English and Khmer situation summaries.
        """
        high_factors_en = []
        high_factors_km = []

        if factors.get("rainfall", {}).get("score", 0) >= 50.0:
            high_factors_en.append(f"significant precipitation ({factors['rainfall'].get('rain_7d', 0):.1f}mm in 7 days)")
            high_factors_km.append(f"កម្រិតទឹកភ្លៀងខ្ពស់ ({factors['rainfall'].get('rain_7d', 0):.1f} ម.ម ក្នុង ៧ ថ្ងៃ)")

        if factors.get("hydrology", {}).get("score", 0) >= 50.0:
            high_factors_en.append(f"elevated river discharge ({factors['hydrology'].get('discharge_m3s', 0):.0f} m³/s)")
            high_factors_km.append(f"លំហូរទឹកទន្លេកើនឡើងខ្លាំង ({factors['hydrology'].get('discharge_m3s', 0):.0f} ម៉ែត្រគូប/វិនាទី)")

        if factors.get("soil", {}).get("score", 0) >= 60.0:
            high_factors_en.append("near-saturated soil conditions limiting infiltration")
            high_factors_km.append("សំណើមដីជិតឆ្អែត កាត់បន្ថយការជ្រាបទឹកចូលដី")

        if factors.get("seasonal", {}).get("score", 0) >= 70.0:
            high_factors_en.append("peak Tonle Sap monsoon expansion pulse")
            high_factors_km.append("រដូវកាលឡើងទឹកខ្ពស់បំផុតនៃបឹងទន្លេសាប")

        reasons_en = ", ".join(high_factors_en) if high_factors_en else "nominal meteorological and hydrological conditions"
        reasons_km = ", ".join(high_factors_km) if high_factors_km else "លក្ខខណ្ឌឧតុនិយម និងជលសាស្ត្រធម្មតា"

        if category == "Very High":
            en = (
                f"CRITICAL FLOOD RISK ({probability:.1f}%) in {location_name}, {province}. "
                f"Severe inundation is imminent driven by {reasons_en}. "
                f"Immediate response: mobilize community rescue teams and evacuate vulnerable floodplain zones."
            )
            km = (
                f"ហានិភ័យទឹកជំនន់ធ្ងន់ធ្ងរបំផុត ({probability:.1f}%) នៅ{location_name} ខេត្ត{province}។ "
                f"ការជន់លិចធ្ងន់ធ្ងរជិតកើតមានឡើងដោយសារ {reasons_km}។ "
                f"វិធានការជាបន្ទាន់៖ ចល័តក្រុមសង្គ្រោះសហគមន៍ និងជម្លៀសប្រជាពលរដ្ឋចេញពីតំបន់ទំនាបងាយរងគ្រោះ។"
            )
        elif category == "High":
            en = (
                f"HIGH FLOOD RISK ({probability:.1f}%) in {location_name}, {province}. "
                f"Rising water levels driven by {reasons_en}. "
                f"Precautionary response: secure agricultural equipment, reinforce embankments, and prepare evacuation shelters."
            )
            km = (
                f"ហានិភ័យទឹកជំនន់កម្រិតខ្ពស់ ({probability:.1f}%) នៅ{location_name} ខេត្ត{province}។ "
                f"កម្ពស់ទឹកកំពុងកើនឡើងដោយសារ {reasons_km}។ "
                f"វិធានការប្រុងប្រយ័ត្ន៖ ការពារឧបករណ៍កសិកម្ម ពង្រឹងទំនប់ទឹក និងរៀបចំទីទួលសុវត្ថិភាព។"
            )
        elif category == "Moderate":
            en = (
                f"MODERATE FLOOD WATCH ({probability:.1f}%) in {location_name}, {province}. "
                f"Moderate hydrological pressure noted due to {reasons_en}. "
                f"Local authorities and farmers should maintain standard vigilance and track lake telemetry."
            )
            km = (
                f"ការប្រុងប្រយ័ត្នទឹកជំនន់កម្រិតមធ្យម ({probability:.1f}%) នៅ{location_name} ខេត្ត{province}។ "
                f"សម្ពាធជលសាស្ត្រមធ្យមត្រូវបានកត់សម្គាល់ដោយសារ {reasons_km}។ "
                f"អាជ្ញាធរមូលដ្ឋាន និងកសិករគួរតែបន្តការប្រុងប្រយ័ត្ន និងតាមដានទិន្នន័យកម្ពស់ទឹកបឹង។"
            )
        else:
            en = (
                f"LOW FLOOD RISK ({probability:.1f}%) in {location_name}, {province}. "
                f"Conditions are stable with {reasons_en}. Hydrological systems remain within safe buffer margins."
            )
            km = (
                f"ហានិភ័យទឹកជំនន់កម្រិតទាប ({probability:.1f}%) នៅ{location_name} ខេត្ត{province}។ "
                f"ស្ថានភាពមានស្ថេរភាពជាមួយ {reasons_km}។ ប្រព័ន្ធជលសាស្ត្រស្ថិតក្នុងកម្រិតសុវត្ថិភាព។"
            )

        return en, km

    async def assess_location(
        self,
        location_id: int,
        db: aiosqlite.Connection,
        prediction_horizon_days: int = 7
    ) -> Dict[str, Any]:
        """
        Assess real-time flood risk for a specific monitoring location by querying the database.
        """
        # 1. Fetch location details
        cursor = await db.execute(
            "SELECT id, name, name_km, province, flood_frequency_score, lat, lon FROM monitoring_locations WHERE id = ?",
            (location_id,)
        )
        location = await cursor.fetchone()
        if not location:
            # Fallback to config preset if not found in db table
            loc_key = [k for k, v in settings.MONITORING_LOCATIONS.items() if v["id"] == location_id]
            if loc_key:
                cfg = settings.MONITORING_LOCATIONS[loc_key[0]]
                location = {
                    "id": cfg["id"],
                    "name": cfg["name"],
                    "name_km": cfg["name_km"],
                    "province": cfg["province"],
                    "flood_frequency_score": cfg["flood_frequency_score"],
                    "lat": cfg["lat"],
                    "lon": cfg["lon"]
                }
            else:
                raise ValueError(f"Monitoring location with ID {location_id} not found.")

        # 2. Fetch latest rainfall data (past 3, 7, 30 days)
        # Sum precipitation_mm or rain_mm
        now = datetime.now(timezone.utc)
        iso_3d = (now - timedelta(days=3)).isoformat()
        iso_7d = (now - timedelta(days=7)).isoformat()
        iso_30d = (now - timedelta(days=30)).isoformat()

        # Query recent weather observations
        weather_cursor = await db.execute(
            """
            SELECT 
                COALESCE(SUM(CASE WHEN timestamp >= ? THEN precipitation_mm ELSE 0 END), 0.0) as rain_3d,
                COALESCE(SUM(CASE WHEN timestamp >= ? THEN precipitation_mm ELSE 0 END), 0.0) as rain_7d,
                COALESCE(SUM(precipitation_mm), 0.0) as rain_30d,
                AVG(soil_moisture) as avg_soil_moisture
            FROM weather_data 
            WHERE location_id = ? AND timestamp >= ?
            """,
            (iso_3d, iso_7d, location_id, iso_30d)
        )
        w_row = await weather_cursor.fetchone()
        rain_3d = float(w_row["rain_3d"]) if w_row and w_row["rain_3d"] is not None else 0.0
        rain_7d = float(w_row["rain_7d"]) if w_row and w_row["rain_7d"] is not None else 0.0
        rain_30d = float(w_row["rain_30d"]) if w_row and w_row["rain_30d"] is not None else 0.0
        soil_m = float(w_row["avg_soil_moisture"]) if w_row and w_row["avg_soil_moisture"] is not None else 0.32

        # 3. Fetch latest river discharge
        discharge_cursor = await db.execute(
            """
            SELECT discharge_m3s, discharge_max, date 
            FROM river_discharge 
            WHERE location_id = ? 
            ORDER BY date DESC LIMIT 1
            """,
            (location_id,)
        )
        d_row = await discharge_cursor.fetchone()
        discharge_m3s = float(d_row["discharge_m3s"]) if d_row and d_row["discharge_m3s"] is not None else 850.0

        # Also check nearest station water level if available
        station_cursor = await db.execute(
            """
            SELECT wl.value, s.alarm_level, s.flood_level 
            FROM water_levels wl
            JOIN stations s ON wl.station_id = s.id
            WHERE s.province LIKE ? OR s.is_active = 1
            ORDER BY wl.timestamp DESC LIMIT 1
            """,
            (f"%{location['province']}%",)
        )
        st_row = await station_cursor.fetchone()
        water_level_m = float(st_row["value"]) if st_row and st_row["value"] is not None else None
        alarm_level_m = float(st_row["alarm_level"]) if st_row and st_row["alarm_level"] is not None else None

        # 4. Compute Factor Scores
        rainfall_score = self.compute_rainfall_score(rain_3d, rain_7d, rain_30d)
        hydro_score = self.compute_hydro_score(
            discharge_m3s=discharge_m3s,
            water_level_m=water_level_m,
            alarm_level_m=alarm_level_m
        )
        soil_score = self.compute_soil_score(soil_m)
        seasonal_score = self.compute_seasonal_factor(now)

        # Historical baseline score (from database location attribute)
        hist_baseline = float(location["flood_frequency_score"] or 0.65) * 100.0
        historical_score = round(min(max(hist_baseline, 0.0), 100.0), 2)

        # 5. Calculate Weighted Total Probability
        risk_probability = (
            (rainfall_score * self.WEIGHT_RAINFALL) +
            (hydro_score * self.WEIGHT_HYDRO) +
            (soil_score * self.WEIGHT_SOIL) +
            (seasonal_score * self.WEIGHT_SEASONAL) +
            (historical_score * self.WEIGHT_HISTORICAL)
        )
        risk_probability = round(float(min(max(risk_probability, 0.0), 100.0)), 1)
        category = self.classify_category(risk_probability)

        contributing_factors = {
            "rainfall": {
                "score": rainfall_score,
                "weight": self.WEIGHT_RAINFALL,
                "weighted_contribution": round(rainfall_score * self.WEIGHT_RAINFALL, 2),
                "rain_3d_mm": round(rain_3d, 1),
                "rain_7d_mm": round(rain_7d, 1),
                "rain_30d_mm": round(rain_30d, 1)
            },
            "hydrology": {
                "score": hydro_score,
                "weight": self.WEIGHT_HYDRO,
                "weighted_contribution": round(hydro_score * self.WEIGHT_HYDRO, 2),
                "discharge_m3s": round(discharge_m3s, 1),
                "water_level_m": water_level_m,
                "alarm_level_m": alarm_level_m
            },
            "soil": {
                "score": soil_score,
                "weight": self.WEIGHT_SOIL,
                "weighted_contribution": round(soil_score * self.WEIGHT_SOIL, 2),
                "soil_moisture_vol": round(soil_m, 3)
            },
            "seasonal": {
                "score": seasonal_score,
                "weight": self.WEIGHT_SEASONAL,
                "weighted_contribution": round(seasonal_score * self.WEIGHT_SEASONAL, 2),
                "day_of_year": now.timetuple().tm_yday
            },
            "historical": {
                "score": historical_score,
                "weight": self.WEIGHT_HISTORICAL,
                "weighted_contribution": round(historical_score * self.WEIGHT_HISTORICAL, 2),
                "province_vulnerability": location["flood_frequency_score"]
            }
        }

        explanation_en, explanation_km = self.generate_explanations(
            category=category,
            probability=risk_probability,
            factors=contributing_factors,
            location_name=location["name"],
            province=location["province"]
        )

        assessment_record = {
            "location_id": location_id,
            "location_name": location["name"],
            "location_name_km": location["name_km"],
            "province": location["province"],
            "assessment_date": now.isoformat(),
            "prediction_horizon_days": prediction_horizon_days,
            "risk_probability": risk_probability,
            "risk_category": category,
            "model_version": "v1.2.0-tonle-calibrated",
            "model_type": "MultiFactorRuleEngine",
            "contributing_factors": contributing_factors,
            "explanation_en": explanation_en,
            "explanation_km": explanation_km
        }

        # 6. Save or update record in database
        await db.execute(
            """
            INSERT INTO risk_assessments (
                location_id, assessment_date, prediction_horizon_days,
                risk_probability, risk_category, model_version, model_type,
                contributing_factors_json, confidence_info_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                location_id,
                now.isoformat(),
                prediction_horizon_days,
                risk_probability,
                category,
                "v1.2.0-tonle-calibrated",
                "MultiFactorRuleEngine",
                json.dumps(contributing_factors),
                json.dumps({
                    "explanation_en": explanation_en,
                    "explanation_km": explanation_km,
                    "data_freshness": now.isoformat()
                }),
                now.isoformat()
            )
        )
        await db.commit()

        return assessment_record

    async def assess_all_locations(self, db: aiosqlite.Connection) -> List[Dict[str, Any]]:
        """
        Run assessments across all 5 monitored Tonle Sap provinces.
        """
        cursor = await db.execute("SELECT id FROM monitoring_locations ORDER BY id ASC")
        rows = await cursor.fetchall()
        results = []
        for row in rows:
            try:
                res = await self.assess_location(row["id"], db)
                results.append(res)
            except Exception as e:
                logger.error(f"Error assessing risk for location {row['id']}: {e}")
        return results


risk_engine = RiskEngine()
