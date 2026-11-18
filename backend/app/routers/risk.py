"""
FloodPulse AI - Predictive Risk & Early Warning Assessment API Router
Exposes multi-factor risk calculations, bilingual explanations, and operational thresholds.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

import aiosqlite
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.database import get_db
from app.services.risk_engine import risk_engine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/risk", tags=["Risk Assessment"])


class FactorContribution(BaseModel):
    score: float
    weight: float
    weighted_contribution: float


class RiskDetailResponse(BaseModel):
    location_id: int
    location_name: str
    location_name_km: Optional[str]
    province: str
    assessment_date: str
    prediction_horizon_days: int
    risk_probability: float
    risk_category: str
    model_version: str
    model_type: str
    contributing_factors: Dict[str, Any]
    explanation_en: str
    explanation_km: str


class AssessTriggerRequest(BaseModel):
    location_id: Optional[int] = Field(None, description="Optional specific location ID to assess, or None for all")
    prediction_horizon_days: int = Field(7, ge=1, le=14)


class ModelInfoResponse(BaseModel):
    model_name: str
    version: str
    framework: str
    calibrated_for: str
    features_used: List[str]
    factor_weights: Dict[str, float]
    training_data_baseline: str
    operational_status: str


class ThresholdsResponse(BaseModel):
    categories: Dict[str, Dict[str, Any]]
    recommended_actions: Dict[str, Dict[str, str]]


@router.get("/assessments", response_model=List[RiskDetailResponse])
async def list_current_risk_assessments(
    db: aiosqlite.Connection = Depends(get_db)
) -> List[RiskDetailResponse]:
    """
    Retrieve the most recent flood risk assessments across all monitored Tonle Sap provinces.
    """
    cursor = await db.execute("SELECT id FROM monitoring_locations ORDER BY id ASC")
    loc_rows = await cursor.fetchall()
    results = []

    for loc in loc_rows:
        loc_id = loc["id"]
        # Fetch latest assessment
        q = """
            SELECT r.id, r.location_id, r.assessment_date, r.prediction_horizon_days,
                   r.risk_probability, r.risk_category, r.model_version, r.model_type,
                   r.contributing_factors_json, r.confidence_info_json,
                   m.name as location_name, m.name_km as location_name_km, m.province
            FROM risk_assessments r
            JOIN monitoring_locations m ON r.location_id = m.id
            WHERE r.location_id = ?
            ORDER BY r.id DESC LIMIT 1
        """
        r_cursor = await db.execute(q, (loc_id,))
        row = await r_cursor.fetchone()

        if row:
            factors = json.loads(row["contributing_factors_json"] or "{}")
            conf = json.loads(row["confidence_info_json"] or "{}")
            results.append(RiskDetailResponse(
                location_id=row["location_id"],
                location_name=row["location_name"],
                location_name_km=row["location_name_km"],
                province=row["province"],
                assessment_date=row["assessment_date"],
                prediction_horizon_days=row["prediction_horizon_days"] or 7,
                risk_probability=float(row["risk_probability"]),
                risk_category=row["risk_category"],
                model_version=row["model_version"] or "v1.2.0",
                model_type=row["model_type"] or "MultiFactorRuleEngine",
                contributing_factors=factors,
                explanation_en=conf.get("explanation_en", ""),
                explanation_km=conf.get("explanation_km", "")
            ))
        else:
            # If not yet assessed, compute dynamically
            ass = await risk_engine.assess_location(loc_id, db)
            results.append(RiskDetailResponse(**ass))

    return results


@router.get("/assessments/{location_id}", response_model=RiskDetailResponse)
async def get_location_risk_assessment(
    location_id: int,
    db: aiosqlite.Connection = Depends(get_db)
) -> RiskDetailResponse:
    """
    Retrieve detailed risk assessment, factor weights, and bilingual advisory for a single province.
    """
    q = """
        SELECT r.id, r.location_id, r.assessment_date, r.prediction_horizon_days,
               r.risk_probability, r.risk_category, r.model_version, r.model_type,
               r.contributing_factors_json, r.confidence_info_json,
               m.name as location_name, m.name_km as location_name_km, m.province
        FROM risk_assessments r
        JOIN monitoring_locations m ON r.location_id = m.id
        WHERE r.location_id = ?
        ORDER BY r.id DESC LIMIT 1
    """
    cursor = await db.execute(q, (location_id,))
    row = await cursor.fetchone()

    if not row:
        # Compute real-time
        try:
            ass = await risk_engine.assess_location(location_id, db)
            return RiskDetailResponse(**ass)
        except Exception as e:
            raise HTTPException(status_code=404, detail=f"Location {location_id} not found or assessment failed: {e}")

    factors = json.loads(row["contributing_factors_json"] or "{}")
    conf = json.loads(row["confidence_info_json"] or "{}")

    return RiskDetailResponse(
        location_id=row["location_id"],
        location_name=row["location_name"],
        location_name_km=row["location_name_km"],
        province=row["province"],
        assessment_date=row["assessment_date"],
        prediction_horizon_days=row["prediction_horizon_days"] or 7,
        risk_probability=float(row["risk_probability"]),
        risk_category=row["risk_category"],
        model_version=row["model_version"] or "v1.2.0",
        model_type=row["model_type"] or "MultiFactorRuleEngine",
        contributing_factors=factors,
        explanation_en=conf.get("explanation_en", ""),
        explanation_km=conf.get("explanation_km", "")
    )


@router.post("/assess", status_code=status.HTTP_200_OK)
async def trigger_risk_assessment(
    payload: AssessTriggerRequest,
    db: aiosqlite.Connection = Depends(get_db)
) -> Dict[str, Any]:
    """
    On-demand execution of the flood risk assessment engine.
    Computes updated probabilities and broadcasts alerts if thresholds are exceeded.
    """
    if payload.location_id:
        res = await risk_engine.assess_location(
            location_id=payload.location_id,
            db=db,
            prediction_horizon_days=payload.prediction_horizon_days
        )
        return {
            "status": "success",
            "triggered_count": 1,
            "results": [res]
        }
    else:
        results = await risk_engine.assess_all_locations(db)
        return {
            "status": "success",
            "triggered_count": len(results),
            "results": results
        }


@router.get("/model-info", response_model=ModelInfoResponse)
async def get_model_info() -> ModelInfoResponse:
    """
    Retrieve architecture, feature schema, and factor weights of the active flood early warning engine.
    """
    return ModelInfoResponse(
        model_name="FloodPulse Tonle Sap Calibrated Hybrid Engine",
        version="v1.2.0-tonle-calibrated",
        framework="Multi-Factor Hydro-Meteorological Rule Engine + Random Forest Classifier",
        calibrated_for="Tonle Sap Lake Reversal System & Lower Mekong Floodplains",
        features_used=[
            "rainfall_3d (Flash flood potential)",
            "rainfall_7d (Catchment accumulation)",
            "rainfall_30d (Antecedent precipitation API)",
            "discharge_current (River flux m³/s)",
            "water_level_m (Gauging station telemetry)",
            "soil_moisture (Volumetric topsoil saturation)",
            "seasonal_pulse (Mekong annual pulse curve)",
            "flood_frequency_historical (Disaster recurrence)"
        ],
        factor_weights={
            "Hydrology (Discharge & Water Level)": risk_engine.WEIGHT_HYDRO,
            "Rainfall (3d, 7d, 30d Cumulative)": risk_engine.WEIGHT_RAINFALL,
            "Soil Moisture (Saturation Ratio)": risk_engine.WEIGHT_SOIL,
            "Seasonal Monsoon Cycle (Mekong Pulse)": risk_engine.WEIGHT_SEASONAL,
            "Historical Vulnerability (Disaster Archive)": risk_engine.WEIGHT_HISTORICAL
        },
        training_data_baseline="Historical Cambodia National Disaster Management Committee (NCDM) flood events (2000-2023) + Open-Meteo & GloFAS reanalysis",
        operational_status="Active & Calibrated"
    )


@router.get("/thresholds", response_model=ThresholdsResponse)
async def get_risk_thresholds() -> ThresholdsResponse:
    """
    Retrieve operational risk category boundaries and standard operating procedures (SOPs).
    """
    categories = {
        "Low": {
            "range": [0.0, 25.0],
            "color": "#10B981",
            "tag_en": "Normal Baseline",
            "tag_km": "ស្ថានភាពធម្មតា",
            "description": "Hydrological indicators within standard seasonal parameters."
        },
        "Moderate": {
            "range": [25.0, 50.0],
            "color": "#F59E0B",
            "tag_en": "Flood Advisory",
            "tag_km": "ការប្រុងប្រយ័ត្ន",
            "description": "Elevated soil moisture or rising river discharge. Agricultural vigilance advised."
        },
        "High": {
            "range": [50.0, 75.0],
            "color": "#F97316",
            "tag_en": "Flood Warning",
            "tag_km": "ការព្រមានទឹកជំនន់",
            "description": "High probability of low-lying floodplain and tributary inundation."
        },
        "Very High": {
            "range": [75.0, 100.0],
            "color": "#EF4444",
            "tag_en": "Critical Emergency",
            "tag_km": "អាសន្នធ្ងន់ធ្ងរ",
            "description": "Severe inundation imminent or underway. Immediate evacuation required."
        }
    }

    actions = {
        "Low": {
            "action_en": "Maintain routine observation and lake level tracking.",
            "action_km": "បន្តការតាមដានជាប្រចាំនូវកម្ពស់ទឹកបឹងទន្លេសាប។"
        },
        "Moderate": {
            "action_en": "Secure vulnerable agricultural machinery, inspect river dykes, and verify emergency communication channels.",
            "action_km": "ការពារគ្រឿងចក្រកសិកម្ម ត្រួតពិនិត្យទំនប់ទឹក និងផ្ទៀងផ្ទាត់បណ្តាញទំនាក់ទំនងបន្ទាន់។"
        },
        "High": {
            "action_en": "Alert village chiefs, prepare community safe mounds (Toul Sopheakpheap), and stage rescue boats.",
            "action_km": "ជូនដំណឹងដល់មេភូមិ រៀបចំទីទួលសុវត្ថិភាពសហគមន៍ និងត្រៀមទូកសង្គ្រោះ។"
        },
        "Very High": {
            "action_en": "Execute community evacuation protocols immediately. Relocate elderly, children, and livestock to designated high ground.",
            "action_km": "អនុវត្តផែនការជម្លៀសប្រជាពលរដ្ឋជាបន្ទាន់។ ផ្លាស់ទីមនុស្សចាស់ កុមារ និងសត្វពាហនៈទៅកាន់ទីទួលសុវត្ថិភាព។"
        }
    }

    return ThresholdsResponse(categories=categories, recommended_actions=actions)
