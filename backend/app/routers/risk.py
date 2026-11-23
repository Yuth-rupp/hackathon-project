
"""
FloodPulse AI - Flood Risk Assessment API

The active engine is a weighted rule-based model.
It is not a trained CatBoost or Random Forest probability model.
"""

import json
import logging
from typing import Any, Dict, List, Optional

import aiosqlite
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.database import get_db
from app.services.risk_engine import risk_engine

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/risk",
    tags=["Risk Assessment"],
)


# ---------------------------------------------------------
# Request and response models
# ---------------------------------------------------------

class AssessTriggerRequest(BaseModel):
    location_id: Optional[int] = Field(
        default=None,
        description="Location ID. Leave empty to assess all locations.",
    )
    prediction_horizon_days: int = Field(
        default=7,
        ge=1,
        le=14,
    )


class RiskDetailResponse(BaseModel):
    id: Optional[int] = None

    location_id: int
    location_name: str
    location_name_km: Optional[str] = None
    province: str

    assessment_date: str
    prediction_horizon_days: int = 7

    risk_score: float
    risk_probability: float
    risk_category: str

    primary_driver: Optional[str] = None

    model_version: str
    model_type: str

    contributing_factors: Dict[str, Any] = Field(
        default_factory=dict
    )

    data_coverage_percent: Optional[float] = None
    data_status: Optional[str] = None
    data_freshness: Dict[str, Any] = Field(
        default_factory=dict
    )

    explanation_en: str = ""
    explanation_km: str = ""


class ModelInfoResponse(BaseModel):
    model_name: str
    version: str
    framework: str
    probability_calibrated: bool
    factor_weights: Dict[str, float]
    operational_status: str


class ThresholdsResponse(BaseModel):
    categories: Dict[str, Dict[str, Any]]
    recommended_actions: Dict[str, str]


# ---------------------------------------------------------
# Helpers
# ---------------------------------------------------------

def _safe_json(value: Optional[str]) -> Dict[str, Any]:
    """Decode a JSON database field safely."""

    if not value:
        return {}

    try:
        result = json.loads(value)
        return result if isinstance(result, dict) else {}
    except (json.JSONDecodeError, TypeError):
        logger.warning("Could not decode a risk assessment JSON field.")
        return {}


def _build_saved_assessment(
    row: aiosqlite.Row,
) -> RiskDetailResponse:
    """Convert a saved database assessment into the API response."""

    factors = _safe_json(row["contributing_factors_json"])
    confidence = _safe_json(row["confidence_info_json"])

    score = float(row["risk_probability"] or 0.0)

    return RiskDetailResponse(
        id=row["id"],
        location_id=row["location_id"],
        location_name=row["location_name"],
        location_name_km=row["location_name_km"],
        province=row["province"],
        assessment_date=row["assessment_date"],
        prediction_horizon_days=(
            row["prediction_horizon_days"] or 7
        ),
        risk_score=score,
        # Legacy field: this is a score, not a calibrated probability.
        risk_probability=score,
        risk_category=row["risk_category"],
        primary_driver=confidence.get("primary_driver"),
        model_version=(
            row["model_version"] or "legacy"
        ),
        model_type=(
            row["model_type"] or "legacy"
        ),
        contributing_factors=factors,
        data_coverage_percent=confidence.get(
            "data_coverage_percent"
        ),
        data_status=confidence.get("data_status"),
        data_freshness=confidence.get(
            "data_freshness", {}
        ),
        explanation_en=confidence.get(
            "explanation_en", ""
        ),
        explanation_km=confidence.get(
            "explanation_km", ""
        ),
    )


async def _get_latest_saved_assessment(
    db: aiosqlite.Connection,
    location_id: int,
) -> Optional[RiskDetailResponse]:
    cursor = await db.execute(
        """
        SELECT
            r.id,
            r.location_id,
            r.assessment_date,
            r.prediction_horizon_days,
            r.risk_probability,
            r.risk_category,
            r.model_version,
            r.model_type,
            r.contributing_factors_json,
            r.confidence_info_json,
            m.name AS location_name,
            m.name_km AS location_name_km,
            m.province
        FROM risk_assessments r
        INNER JOIN monitoring_locations m
            ON m.id = r.location_id
        WHERE r.location_id = ?
        ORDER BY r.id DESC
        LIMIT 1
        """,
        (location_id,),
    )

    row = await cursor.fetchone()

    if row is None:
        return None

    return _build_saved_assessment(row)


async def _get_location_ids(
    db: aiosqlite.Connection,
) -> List[int]:
    cursor = await db.execute(
        """
        SELECT id
        FROM monitoring_locations
        ORDER BY id ASC
        """
    )

    rows = await cursor.fetchall()
    return [int(row["id"]) for row in rows]


async def _get_or_calculate_assessment(
    db: aiosqlite.Connection,
    location_id: int,
) -> RiskDetailResponse:
    """
    Reuse a saved assessment only when it was generated
    by the currently active model version.
    """

    saved = await _get_latest_saved_assessment(
        db,
        location_id,
    )

    if (
        saved is not None
        and saved.model_version == risk_engine.MODEL_VERSION
    ):
        return saved

    calculated = await risk_engine.assess_location(
        location_id=location_id,
        db=db,
        prediction_horizon_days=7,
    )

    return RiskDetailResponse(**calculated)


# ---------------------------------------------------------
# Current risk assessments
# ---------------------------------------------------------

@router.get(
    "/assessments",
    response_model=List[RiskDetailResponse],
)
async def list_current_risk_assessments(
    db: aiosqlite.Connection = Depends(get_db),
) -> List[RiskDetailResponse]:
    """
    Return the latest assessment for every monitoring location.

    Old model-version records are recalculated using the active engine.
    """

    location_ids = await _get_location_ids(db)
    results: List[RiskDetailResponse] = []

    for location_id in location_ids:
        try:
            assessment = await _get_or_calculate_assessment(
                db,
                location_id,
            )
            results.append(assessment)

        except Exception:
            logger.exception(
                "Unable to retrieve risk assessment for location %s",
                location_id,
            )

    return results


# ---------------------------------------------------------
# Individual location assessment
# ---------------------------------------------------------

@router.get(
    "/assessments/{location_id}",
    response_model=RiskDetailResponse,
)
async def get_location_risk_assessment(
    location_id: int,
    db: aiosqlite.Connection = Depends(get_db),
) -> RiskDetailResponse:

    cursor = await db.execute(
        """
        SELECT id
        FROM monitoring_locations
        WHERE id = ?
        """,
        (location_id,),
    )

    location = await cursor.fetchone()

    if location is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Monitoring location {location_id} was not found.",
        )

    try:
        return await _get_or_calculate_assessment(
            db,
            location_id,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        logger.exception(
            "Risk assessment failed for location %s",
            location_id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to calculate the risk assessment.",
        ) from exc


# ---------------------------------------------------------
# Trigger a new assessment
# ---------------------------------------------------------

@router.post(
    "/assess",
    status_code=status.HTTP_200_OK,
)
async def trigger_risk_assessment(
    payload: AssessTriggerRequest,
    db: aiosqlite.Connection = Depends(get_db),
) -> Dict[str, Any]:

    try:
        if payload.location_id is not None:
            result = await risk_engine.assess_location(
                location_id=payload.location_id,
                db=db,
                prediction_horizon_days=payload.prediction_horizon_days,
            )

            return {
                "status": "success",
                "triggered_count": 1,
                "results": [result],
            }

        results = await risk_engine.assess_all_locations(db)

        return {
            "status": "success",
            "triggered_count": len(results),
            "results": results,
        }

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        logger.exception("On-demand risk assessment failed.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Risk assessment could not be completed.",
        ) from exc


# ---------------------------------------------------------
# Model information
# ---------------------------------------------------------

@router.get(
    "/model-info",
    response_model=ModelInfoResponse,
)
async def get_model_info() -> ModelInfoResponse:

    return ModelInfoResponse(
        model_name="FloodPulse Multi-Factor Flood Risk Engine",
        version=risk_engine.MODEL_VERSION,
        framework="Weighted Rule-Based Hydro-Meteorological Model",
        probability_calibrated=False,
        factor_weights=risk_engine.WEIGHTS,
        operational_status="operational",
    )


# ---------------------------------------------------------
# Risk thresholds
# ---------------------------------------------------------

@router.get(
    "/thresholds",
    response_model=ThresholdsResponse,
)
async def get_risk_thresholds() -> ThresholdsResponse:

    return ThresholdsResponse(
        categories={
            "Low": {
                "minimum": 0,
                "maximum": 24.99,
            },
            "Moderate": {
                "minimum": 25,
                "maximum": 49.99,
            },
            "High": {
                "minimum": 50,
                "maximum": 74.99,
            },
            "Very High": {
                "minimum": 75,
                "maximum": 100,
            },
        },
        recommended_actions={
            "Low": "Continue routine monitoring.",
            "Moderate": (
                "Monitor rainfall and river conditions regularly."
            ),
            "High": (
                "Prepare flood response resources and alert "
                "vulnerable communities."
            ),
            "Very High": (
                "Prioritize emergency response and assess "
                "evacuation needs."
            ),
        },
    )
