"""
FloodPulse AI - Operational Administration & Configuration API Router
Provides station management CRUD, connector mass refresh, security audit logging,
runtime threshold calibration, Telegram configuration, and ML model performance reports.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

import aiosqlite
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.database import get_db
from app.config import settings
from app.services.scheduler import fetch_weather_job, fetch_discharge_job, fetch_satellite_job
from app.services.risk_engine import risk_engine
from app.services.telegram import telegram_service
from app.ml.training import prepare_training_data, train_random_forest
from app.ml.evaluation import evaluate_model, generate_report

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["Administration"])


# ==============================================================================
# Request & Response Schemas
# ==============================================================================
class StationCreateRequest(BaseModel):
    code: str = Field(..., description="Unique station alphanumeric code, e.g. 020108")
    name: str = Field(..., description="Station English name")
    name_km: Optional[str] = None
    type: str = Field("hydrological", description="Station gauge type")
    province: str
    district: Optional[str] = None
    lat: float
    lon: float
    elevation: Optional[float] = None
    water_body: str = Field("Tonle Sap Lake", description="Associated river or lake body")
    data_source: str = "MRC"
    alarm_level: float = Field(..., description="Warning water level threshold (m)")
    flood_level: float = Field(..., description="Critical emergency flood level (m)")
    is_active: bool = True
    notes: Optional[str] = None


class StationUpdateRequest(BaseModel):
    name: Optional[str] = None
    name_km: Optional[str] = None
    lat: Optional[float] = None
    lon: Optional[float] = None
    alarm_level: Optional[float] = None
    flood_level: Optional[float] = None
    is_active: Optional[bool] = None
    notes: Optional[str] = None


class RiskThresholdUpdateRequest(BaseModel):
    weight_rainfall: float = Field(..., ge=0.0, le=1.0)
    weight_hydro: float = Field(..., ge=0.0, le=1.0)
    weight_soil: float = Field(..., ge=0.0, le=1.0)
    weight_seasonal: float = Field(..., ge=0.0, le=1.0)
    weight_historical: float = Field(..., ge=0.0, le=1.0)


class TelegramConfigUpdateRequest(BaseModel):
    bot_token: Optional[str] = None
    chat_id: Optional[str] = None
    enabled: bool = True


class AuditLogItem(BaseModel):
    id: int
    action: str
    entity_type: str
    entity_id: Optional[str]
    details: Optional[Dict[str, Any]]
    performed_by: str
    created_at: str


# ==============================================================================
# Station CRUD Endpoints
# ==============================================================================
@router.get("/stations")
async def admin_list_stations(db: aiosqlite.Connection = Depends(get_db)) -> List[Dict[str, Any]]:
    """
    List all hydrological and water level gauging stations with full administrative attributes.
    """
    cursor = await db.execute("SELECT * FROM stations ORDER BY id ASC")
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]


@router.post("/stations", status_code=status.HTTP_201_CREATED)
async def admin_create_station(
    payload: StationCreateRequest,
    db: aiosqlite.Connection = Depends(get_db)
) -> Dict[str, Any]:
    """
    Register a new telemetry monitoring station.
    """
    # Check code uniqueness
    cursor = await db.execute("SELECT id FROM stations WHERE code = ?", (payload.code,))
    if await cursor.fetchone():
        raise HTTPException(status_code=400, detail=f"Station with code '{payload.code}' already exists.")

    now_iso = datetime.now(timezone.utc).isoformat()
    meta_json = json.dumps({"notes": payload.notes or "", "registered_at": now_iso})

    insert_cursor = await db.execute(
        """
        INSERT INTO stations (
            code, name, name_km, type, province, district,
            lat, lon, elevation, water_body, data_source,
            alarm_level, flood_level, is_active, metadata_json, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            payload.code, payload.name, payload.name_km, payload.type,
            payload.province, payload.district, payload.lat, payload.lon,
            payload.elevation, payload.water_body, payload.data_source,
            payload.alarm_level, payload.flood_level, 1 if payload.is_active else 0,
            meta_json, now_iso
        )
    )
    new_id = insert_cursor.lastrowid

    # Record audit log
    await db.execute(
        """
        INSERT INTO audit_log (action, entity_type, entity_id, details_json, performed_by, created_at)
        VALUES ('CREATE_STATION', 'station', ?, ?, 'admin', ?)
        """,
        (str(new_id), json.dumps({"code": payload.code, "name": payload.name}), now_iso)
    )
    await db.commit()

    return {
        "status": "success",
        "station_id": new_id,
        "code": payload.code,
        "message": f"Station '{payload.name}' registered successfully."
    }


@router.put("/stations/{station_id}")
async def admin_update_station(
    station_id: str,
    payload: StationUpdateRequest,
    db: aiosqlite.Connection = Depends(get_db)
) -> Dict[str, Any]:
    """
    Update telemetry thresholds, coordinates, or metadata for an existing station.
    """
    cursor = await db.execute("SELECT * FROM stations WHERE id = ? OR code = ?", (station_id, station_id))
    st = await cursor.fetchone()
    if not st:
        raise HTTPException(status_code=404, detail="Station not found.")

    real_id = st["id"]
    fields = []
    params = []

    if payload.name is not None:
        fields.append("name = ?")
        params.append(payload.name)
    if payload.name_km is not None:
        fields.append("name_km = ?")
        params.append(payload.name_km)
    if payload.lat is not None:
        fields.append("lat = ?")
        params.append(payload.lat)
    if payload.lon is not None:
        fields.append("lon = ?")
        params.append(payload.lon)
    if payload.alarm_level is not None:
        fields.append("alarm_level = ?")
        params.append(payload.alarm_level)
    if payload.flood_level is not None:
        fields.append("flood_level = ?")
        params.append(payload.flood_level)
    if payload.is_active is not None:
        fields.append("is_active = ?")
        params.append(1 if payload.is_active else 0)

    if fields:
        params.append(real_id)
        await db.execute(f"UPDATE stations SET {', '.join(fields)} WHERE id = ?", tuple(params))

    now_iso = datetime.now(timezone.utc).isoformat()
    await db.execute(
        """
        INSERT INTO audit_log (action, entity_type, entity_id, details_json, performed_by, created_at)
        VALUES ('UPDATE_STATION', 'station', ?, ?, 'admin', ?)
        """,
        (str(real_id), json.dumps(payload.model_dump(exclude_none=True)), now_iso)
    )
    await db.commit()

    return {"status": "success", "station_id": real_id, "message": "Station updated successfully."}


@router.delete("/stations/{station_id}")
async def admin_delete_station(
    station_id: str,
    db: aiosqlite.Connection = Depends(get_db)
) -> Dict[str, Any]:
    """
    Remove or deactivate an obsolete gauging station.
    """
    cursor = await db.execute("SELECT id, name FROM stations WHERE id = ? OR code = ?", (station_id, station_id))
    st = await cursor.fetchone()
    if not st:
        raise HTTPException(status_code=404, detail="Station not found.")

    real_id = st["id"]
    await db.execute("DELETE FROM stations WHERE id = ?", (real_id,))

    now_iso = datetime.now(timezone.utc).isoformat()
    await db.execute(
        """
        INSERT INTO audit_log (action, entity_type, entity_id, details_json, performed_by, created_at)
        VALUES ('DELETE_STATION', 'station', ?, ?, 'admin', ?)
        """,
        (str(real_id), json.dumps({"name": st["name"]}), now_iso)
    )
    await db.commit()

    return {"status": "success", "station_id": real_id, "message": "Station deleted successfully."}


# ==============================================================================
# Operational Management Endpoints
# ==============================================================================
@router.post("/refresh-all")
async def admin_refresh_all_connectors(db: aiosqlite.Connection = Depends(get_db)) -> Dict[str, Any]:
    """
    Trigger immediate concurrent refresh across all weather, discharge, satellite, and risk pipelines.
    """
    logger.info("Admin initiated full system pipeline refresh...")
    w_res = await fetch_weather_job()
    d_res = await fetch_discharge_job()
    s_res = await fetch_satellite_job()
    r_res = await risk_engine.assess_all_locations(db)

    now_iso = datetime.now(timezone.utc).isoformat()
    await db.execute(
        """
        INSERT INTO audit_log (action, entity_type, entity_id, details_json, performed_by, created_at)
        VALUES ('REFRESH_ALL', 'system', 'all_connectors', ?, 'admin', ?)
        """,
        (json.dumps({"weather": w_res, "discharge": d_res, "satellite": s_res, "assessments": len(r_res)}), now_iso)
    )
    await db.commit()

    return {
        "status": "success",
        "timestamp": now_iso,
        "weather_refresh": w_res,
        "discharge_refresh": d_res,
        "satellite_refresh": s_res,
        "assessments_updated": len(r_res)
    }


@router.get("/audit-log", response_model=List[AuditLogItem])
async def get_audit_log(
    limit: int = Query(50, ge=1, le=500),
    action: Optional[str] = Query(None),
    db: aiosqlite.Connection = Depends(get_db)
) -> List[AuditLogItem]:
    """
    Retrieve system security and administrative audit trail.
    """
    query = "SELECT id, action, entity_type, entity_id, details_json, performed_by, created_at FROM audit_log"
    params: List[Any] = []
    if action:
        query += " WHERE action LIKE ?"
        params.append(f"%{action}%")

    query += " ORDER BY id DESC LIMIT ?"
    params.append(limit)

    cursor = await db.execute(query, tuple(params))
    rows = await cursor.fetchall()

    results = []
    for r in rows:
        d = None
        if r["details_json"]:
            try:
                d = json.loads(r["details_json"])
            except Exception:
                d = {"raw": r["details_json"]}
        results.append(AuditLogItem(
            id=r["id"],
            action=r["action"],
            entity_type=r["entity_type"],
            entity_id=r["entity_id"],
            details=d,
            performed_by=r["performed_by"] or "system",
            created_at=r["created_at"]
        ))
    return results


@router.put("/risk-thresholds")
async def update_risk_thresholds(
    payload: RiskThresholdUpdateRequest,
    db: aiosqlite.Connection = Depends(get_db)
) -> Dict[str, Any]:
    """
    Calibrate risk factor weights dynamically for seasonal monsoon adaptation.
    """
    total = (
        payload.weight_rainfall + payload.weight_hydro +
        payload.weight_soil + payload.weight_seasonal + payload.weight_historical
    )
    if not (0.98 <= total <= 1.02):
        raise HTTPException(status_code=400, detail=f"Weights must sum to 1.0 (current sum: {total:.3f})")

    # Update engine runtime weights
    risk_engine.WEIGHT_RAINFALL = payload.weight_rainfall
    risk_engine.WEIGHT_HYDRO = payload.weight_hydro
    risk_engine.WEIGHT_SOIL = payload.weight_soil
    risk_engine.WEIGHT_SEASONAL = payload.weight_seasonal
    risk_engine.WEIGHT_HISTORICAL = payload.weight_historical

    now_iso = datetime.now(timezone.utc).isoformat()
    await db.execute(
        """
        INSERT INTO audit_log (action, entity_type, entity_id, details_json, performed_by, created_at)
        VALUES ('UPDATE_RISK_WEIGHTS', 'risk_engine', 'weights', ?, 'admin', ?)
        """,
        (json.dumps(payload.model_dump()), now_iso)
    )
    await db.commit()

    return {
        "status": "success",
        "updated_weights": {
            "rainfall": risk_engine.WEIGHT_RAINFALL,
            "hydro": risk_engine.WEIGHT_HYDRO,
            "soil": risk_engine.WEIGHT_SOIL,
            "seasonal": risk_engine.WEIGHT_SEASONAL,
            "historical": risk_engine.WEIGHT_HISTORICAL
        },
        "updated_at": now_iso
    }


@router.put("/telegram-config")
async def update_telegram_configuration(
    payload: TelegramConfigUpdateRequest,
    db: aiosqlite.Connection = Depends(get_db)
) -> Dict[str, Any]:
    """
    Update Telegram Bot credentials and enable/disable automated emergency dispatches.
    """
    if payload.bot_token is not None:
        settings.TELEGRAM_BOT_TOKEN = payload.bot_token
        telegram_service.bot_token = payload.bot_token
        telegram_service.api_base = f"https://api.telegram.org/bot{payload.bot_token}"

    if payload.chat_id is not None:
        settings.TELEGRAM_CHAT_ID = payload.chat_id
        telegram_service.default_chat_id = payload.chat_id

    settings.TELEGRAM_ALERTS_ENABLED = payload.enabled
    telegram_service.enabled = payload.enabled

    now_iso = datetime.now(timezone.utc).isoformat()
    await db.execute(
        """
        INSERT INTO audit_log (action, entity_type, entity_id, details_json, performed_by, created_at)
        VALUES ('UPDATE_TELEGRAM_CONFIG', 'telegram', 'dispatch', ?, 'admin', ?)
        """,
        (json.dumps({"enabled": payload.enabled, "chat_id_set": bool(payload.chat_id)}), now_iso)
    )
    await db.commit()

    return {
        "status": "success",
        "telegram_enabled": settings.TELEGRAM_ALERTS_ENABLED,
        "is_configured": telegram_service.is_configured(),
        "timestamp": now_iso
    }


@router.get("/model-report")
async def get_model_performance_report(db: aiosqlite.Connection = Depends(get_db)) -> Dict[str, Any]:
    """
    Train and evaluate machine learning flood models and return a complete performance diagnostic report.
    """
    X_train, X_test, y_train, y_test = await prepare_training_data(db)
    rf = train_random_forest(X_train, y_train)
    eval_results = evaluate_model(rf, X_test, y_test)
    report = generate_report(eval_results)

    return {
        "report": report["summary"],
        "status": report["status"],
        "metrics": eval_results,
        "dataset": {
            "training_samples": len(X_train),
            "test_samples": len(X_test),
            "split_type": "Chronological (80/20)",
            "monsoon_positive_ratio": round(float(sum(y_train) / len(y_train)), 3)
        },
        "evaluated_at": datetime.now(timezone.utc).isoformat()
    }
