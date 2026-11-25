
"""
FloodPulse AI - Flood Risk Assessment API

Uses the existing weighted rule-based flood risk engine.

Important:
- risk_score is a score from 0 to 100.
- risk_probability is retained for backward compatibility.
- risk_probability is NOT a calibrated statistical probability.
- Saved assessments are reused only for a limited period.
- Old model-version assessments are recalculated.
"""

import json
import logging
from datetime import datetime, timedelta, timezone
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

# A saved assessment is considered reusable for five minutes.
# This avoids returning an old score indefinitely while also
# preventing a new database assessment on every dashboard refresh.
ASSESSMENT_CACHE_SECONDS = 300


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
# JSON helpers
# ---------------------------------------------------------

def _safe_json(value: Optional[str]) -> Dict[str, Any]:
    """
    Decode a JSON database field safely.

    Invalid or missing JSON returns an empty dictionary.
    """

    if not value:
        return {}

    try:
        result = json.loads(value)

        if isinstance(result, dict):
            return result

        return {}

    except (json.JSONDecodeError, TypeError, ValueError):
        logger.warning(
            "Could not decode a risk assessment JSON field."
        )
        return {}


def _parse_assessment_datetime(
    value: Optional[str],
) -> Optional[datetime]:
    """
    Parse an assessment timestamp and normalize it to UTC.

    Invalid timestamps are treated as stale.
    """

    if not value:
        return None

    try:
        parsed = datetime.fromisoformat(
            str(value).strip().replace("Z", "+00:00")
        )

        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)

        return parsed.astimezone(timezone.utc)

    except (ValueError, TypeError, OverflowError):
        return None


def _is_assessment_fresh(
    assessment_date: Optional[str],
) -> bool:
    """
    Return True only when an assessment is within the
    configured cache period.

    Future timestamps are rejected.
    """

    parsed = _parse_assessment_datetime(assessment_date)

    if parsed is None:
        return False

    now = datetime.now(timezone.utc)

    age = now - parsed

    if age < timedelta(seconds=0):
        return False

    return age <= timedelta(
        seconds=ASSESSMENT_CACHE_SECONDS
    )


# ---------------------------------------------------------
# Database conversion
# ---------------------------------------------------------

def _build_saved_assessment(
    row: aiosqlite.Row,
) -> RiskDetailResponse:
    """
    Convert a saved database assessment into the API response.
    """

    factors = _safe_json(
        row["contributing_factors_json"]
    )

    confidence = _safe_json(
        row["confidence_info_json"]
    )

    raw_score = row["risk_probability"]

    try:
        score = float(raw_score or 0.0)
    except (TypeError, ValueError):
        score = 0.0

    # Protect the API from invalid legacy database values.
    score = max(0.0, min(100.0, score))

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

        # Legacy compatibility field.
        # This is NOT a calibrated probability.
        risk_probability=score,

        risk_category=row["risk_category"],

        primary_driver=confidence.get(
            "primary_driver"
        ),

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

        data_status=confidence.get(
            "data_status"
        ),

        data_freshness=confidence.get(
            "data_freshness",
            {},
        ),

        explanation_en=confidence.get(
            "explanation_en",
            "",
        ),

        explanation_km=confidence.get(
            "explanation_km",
            "",
        ),
    )


# ---------------------------------------------------------
# Database queries
# ---------------------------------------------------------

async def _get_latest_saved_assessment(
    db: aiosqlite.Connection,
    location_id: int,
) -> Optional[RiskDetailResponse]:
    """
    Get the latest saved risk assessment for one location.
    """

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
    """
    Return all monitoring location IDs.
    """

    cursor = await db.execute(
        """
        SELECT id
        FROM monitoring_locations
        ORDER BY id ASC
        """
    )

    rows = await cursor.fetchall()

    return [
        int(row["id"])
        for row in rows
    ]


async def _location_exists(
    db: aiosqlite.Connection,
    location_id: int,
) -> bool:
    """
    Check whether a monitoring location exists.
    """

    cursor = await db.execute(
        """
        SELECT id
        FROM monitoring_locations
        WHERE id = ?
        LIMIT 1
        """,
        (location_id,),
    )

    return await cursor.fetchone() is not None


# ---------------------------------------------------------
# Risk assessment calculation
# ---------------------------------------------------------

async def _calculate_assessment(
    db: aiosqlite.Connection,
    location_id: int,
    prediction_horizon_days: int = 7,
) -> RiskDetailResponse:
    """
    Calculate a new assessment using the existing risk engine.
    """

    calculated = await risk_engine.assess_location(
        location_id=location_id,
        db=db,
        prediction_horizon_days=prediction_horizon_days,
    )

    if not isinstance(calculated, dict):
        raise RuntimeError(
            "Risk engine returned an invalid assessment."
        )

    # Ensure the engine returns the fields required by the API.
    required_fields = [
        "location_id",
        "location_name",
        "province",
        "assessment_date",
        "risk_score",
        "risk_probability",
        "risk_category",
        "model_version",
        "model_type",
    ]

    missing_fields = [
        field
        for field in required_fields
        if field not in calculated
    ]

    if missing_fields:
        raise RuntimeError(
            "Risk engine response is missing fields: "
            + ", ".join(missing_fields)
        )

    # Explicitly retain the fact that the score is not
    # a calibrated probability.
    return RiskDetailResponse(
        **calculated
    )


async def _get_or_calculate_assessment(
    db: aiosqlite.Connection,
    location_id: int,
) -> RiskDetailResponse:
    """
    Reuse an assessment only when:

    1. It exists.
    2. It was generated by the active model version.
    3. Its timestamp is within the five-minute cache period.

    Otherwise, calculate a new assessment.
    """

    saved = await _get_latest_saved_assessment(
        db,
        location_id,
    )

    if saved is not None:

        same_model = (
            saved.model_version == risk_engine.MODEL_VERSION
        )

        recent_assessment = _is_assessment_fresh(
            saved.assessment_date
        )

        if same_model and recent_assessment:
            return saved

        if not same_model:
            logger.info(
                "Risk assessment for location %s uses an old "
                "model version. Recalculating.",
                location_id,
            )

        elif not recent_assessment:
            logger.info(
                "Risk assessment for location %s is older than "
                "%s seconds. Recalculating.",
                location_id,
                ASSESSMENT_CACHE_SECONDS,
            )

    return await _calculate_assessment(
        db=db,
        location_id=location_id,
        prediction_horizon_days=7,
    )


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
    Return the latest risk assessment for every monitoring location.

    Old assessments are recalculated when their model version
    or timestamp is no longer valid.
    """

    location_ids = await _get_location_ids(db)

    results: List[RiskDetailResponse] = []

    for location_id in location_ids:

        try:
            assessment = await _get_or_calculate_assessment(
                db=db,
                location_id=location_id,
            )

            results.append(assessment)

        except Exception:
            logger.exception(
                "Unable to retrieve risk assessment "
                "for location %s",
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
    """
    Get the current assessment for one monitoring location.
    """

    exists = await _location_exists(
        db,
        location_id,
    )

    if not exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"Monitoring location {location_id} "
                "was not found."
            ),
        )

    try:
        return await _get_or_calculate_assessment(
            db=db,
            location_id=location_id,
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
# Trigger a new risk assessment
# ---------------------------------------------------------

@router.post(
    "/assess",
    status_code=status.HTTP_200_OK,
)
async def trigger_risk_assessment(
    payload: AssessTriggerRequest,
    db: aiosqlite.Connection = Depends(get_db),
) -> Dict[str, Any]:
    """
    Force a new risk assessment.

    If location_id is supplied, calculate that location.
    Otherwise, calculate all monitoring locations.
    """

    try:

        if payload.location_id is not None:

            exists = await _location_exists(
                db,
                payload.location_id,
            )

            if not exists:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=(
                        f"Monitoring location "
                        f"{payload.location_id} was not found."
                    ),
                )

            result = await risk_engine.assess_location(
                location_id=payload.location_id,
                db=db,
                prediction_horizon_days=(
                    payload.prediction_horizon_days
                ),
            )

            return {
                "status": "success",
                "triggered_count": 1,
                "results": [result],
            }

        # The existing engine's bulk method processes all
        # monitoring locations using its default horizon.
        results = await risk_engine.assess_all_locations(
            db
        )

        return {
            "status": "success",
            "triggered_count": len(results),
            "results": results,
        }

    except HTTPException:
        raise

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        logger.exception(
            "On-demand risk assessment failed."
        )

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
    """
    Return information about the active risk engine.
    """

    return ModelInfoResponse(
        model_name=(
            "FloodPulse Multi-Factor Flood Risk Engine"
        ),

        version=risk_engine.MODEL_VERSION,

        framework=(
            "Weighted Rule-Based Hydro-Meteorological Model"
        ),

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
    """
    Return the risk categories and recommended actions.
    """

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
            "Low": (
                "Continue routine monitoring and check "
                "the latest available observations."
            ),

            "Moderate": (
                "Monitor rainfall and river conditions regularly. "
                "Review local flood preparedness."
            ),

            "High": (
                "Prepare flood response resources and assess "
                "vulnerable communities."
            ),

            "Very High": (
                "Prioritize emergency response and assess "
                "evacuation needs using verified local information."
            ),
        },
    )
