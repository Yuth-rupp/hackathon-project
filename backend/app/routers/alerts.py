"""
FloodPulse AI - Emergency Alerts & Telegram Dispatch API Router
Provides alert querying, acknowledgment, resolution, bilingual template inspect, and manual dispatch.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

import aiosqlite
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.config import settings
from app.database import get_db
from app.services.telegram import telegram_service
from app.services.alert_service import alert_service
from app.services.realtime import broker

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/alerts", tags=["Alerts & Notifications"])


class AlertItem(BaseModel):
    id: int
    alert_type: str
    severity: str
    title: str
    title_km: Optional[str]
    message: str
    message_km: Optional[str]
    location_id: Optional[int]
    province: Optional[str]
    trigger_source: Optional[str]
    status: str
    telegram_sent: bool
    created_at: str
    resolved_at: Optional[str]
    created_by: str


class CreateAlertRequest(BaseModel):
    severity: str = Field(..., description="Low, Moderate, High, or Very High")
    title: str
    title_km: Optional[str] = None
    message: str
    message_km: Optional[str] = None
    location_id: Optional[int] = None
    province: str
    broadcast_telegram: bool = True


class AcknowledgeRequest(BaseModel):
    responder_name: str = Field(
        "Provincial Disaster Management Committee",
        description="Official responder identifying name",
    )
    notes: Optional[str] = None


class ResolveRequest(BaseModel):
    resolution_notes: str
    resolved_by: str = "Disaster Coordinator"


@router.get("", response_model=List[AlertItem])
async def list_alerts(
    severity: Optional[str] = Query(None, description="Filter by severity: Low, Moderate, High, Very High"),
    status: Optional[str] = Query(None, description="Filter by status: active, acknowledged, resolved"),
    location_id: Optional[int] = Query(None, description="Filter by location ID"),
    limit: int = Query(50, ge=1, le=200),
    db: aiosqlite.Connection = Depends(get_db),
) -> List[AlertItem]:
    """
    List disaster alerts and early warning notifications with filtering options.
    """
    query = """
        SELECT id, alert_type, severity, title, title_km, message, message_km,
               location_id, province, trigger_source, status, telegram_sent,
               created_at, resolved_at, created_by
        FROM alerts
    """
    conditions = []
    params: List[Any] = []

    if severity:
        conditions.append("LOWER(severity) = LOWER(?)")
        params.append(severity)
    if status:
        conditions.append("LOWER(status) = LOWER(?)")
        params.append(status)
    if location_id is not None:
        conditions.append("location_id = ?")
        params.append(location_id)

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    query += " ORDER BY id DESC LIMIT ?"
    params.append(limit)

    cursor = await db.execute(query, tuple(params))
    rows = await cursor.fetchall()

    return [
        AlertItem(
            id=r["id"],
            alert_type=r["alert_type"],
            severity=r["severity"],
            title=r["title"],
            title_km=r["title_km"],
            message=r["message"],
            message_km=r["message_km"],
            location_id=r["location_id"],
            province=r["province"],
            trigger_source=r["trigger_source"],
            status=r["status"],
            telegram_sent=bool(r["telegram_sent"]),
            created_at=r["created_at"],
            resolved_at=r["resolved_at"],
            created_by=r["created_by"] or "system",
        )
        for r in rows
    ]


@router.post("", response_model=AlertItem, status_code=status.HTTP_201_CREATED)
async def create_manual_alert(
    payload: CreateAlertRequest,
    db: aiosqlite.Connection = Depends(get_db),
) -> AlertItem:
    """
    Manually dispatch an emergency broadcast alert across dashboard feeds and Telegram subscribers.
    """
    now_iso = datetime.now(timezone.utc).isoformat()
    t_en = payload.title
    t_km = payload.title_km or payload.title
    m_en = payload.message
    m_km = payload.message_km or payload.message

    cursor = await db.execute(
        """
        INSERT INTO alerts (
            alert_type, severity, title, title_km, message, message_km,
            location_id, province, trigger_source, status, telegram_sent,
            created_at, created_by
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'ManualAdminDispatch', 'active', 0, ?, 'admin')
        """,
        (
            "COMMUNITY_EMERGENCY_DISPATCH",
            payload.severity,
            t_en,
            t_km,
            m_en,
            m_km,
            payload.location_id,
            payload.province,
            now_iso,
        ),
    )
    new_id = cursor.lastrowid
    await db.commit()

    alert_dict = {
        "id": new_id,
        "alert_type": "COMMUNITY_EMERGENCY_DISPATCH",
        "severity": payload.severity,
        "title": t_en,
        "title_km": t_km,
        "message": m_en,
        "message_km": m_km,
        "location_id": payload.location_id,
        "province": payload.province,
        "status": "active",
        "created_at": now_iso,
    }

    telegram_sent = False
    if payload.broadcast_telegram and telegram_service.is_configured():
        tg_res = await telegram_service.send_alert(
            alert=alert_dict,
            location_name=payload.province,
        )
        if tg_res.get("success"):
            telegram_sent = True
            await db.execute(
                "UPDATE alerts SET telegram_sent = 1, telegram_message_id = ? WHERE id = ?",
                (str(tg_res.get("message_id")), new_id),
            )
            await db.commit()

    broker.publish(
        "alert_created",
        {
            "alert_id": new_id,
            "severity": payload.severity,
            "province": payload.province,
            "title": t_en,
        },
    )

    return AlertItem(
        id=new_id,
        alert_type="COMMUNITY_EMERGENCY_DISPATCH",
        severity=payload.severity,
        title=t_en,
        title_km=t_km,
        message=m_en,
        message_km=m_km,
        location_id=payload.location_id,
        province=payload.province,
        trigger_source="ManualAdminDispatch",
        status="active",
        telegram_sent=telegram_sent,
        created_at=now_iso,
        resolved_at=None,
        created_by="admin",
    )


@router.put("/{alert_id}/acknowledge")
async def acknowledge_alert(
    alert_id: int,
    payload: Optional[AcknowledgeRequest] = None,
    db: aiosqlite.Connection = Depends(get_db),
) -> Dict[str, Any]:
    """
    Acknowledge an active alert, confirming incident response is actively underway.
    """
    cursor = await db.execute("SELECT id, status FROM alerts WHERE id = ?", (alert_id,))
    alert = await cursor.fetchone()
    if not alert:
        raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found.")

    now_iso = datetime.now(timezone.utc).isoformat()
    responder = payload.responder_name if payload else "Disaster Command Center"

    await db.execute(
        """
        UPDATE alerts
        SET status = 'acknowledged'
        WHERE id = ?
        """,
        (alert_id,),
    )

    await db.execute(
        """
        INSERT INTO audit_log (action, entity_type, entity_id, details_json, performed_by, created_at)
        VALUES ('ACKNOWLEDGE_ALERT', 'alert', ?, ?, ?, ?)
        """,
        (
            str(alert_id),
            json.dumps({"responder": responder, "notes": payload.notes if payload else ""}),
            responder,
            now_iso,
        ),
    )
    await db.commit()

    broker.publish("alert_changed", {"alert_id": alert_id, "status": "acknowledged"})

    return {
        "status": "success",
        "alert_id": alert_id,
        "new_status": "acknowledged",
        "acknowledged_by": responder,
        "timestamp": now_iso,
    }


@router.put("/{alert_id}/resolve")
async def resolve_alert(
    alert_id: int,
    payload: Optional[ResolveRequest] = None,
    db: aiosqlite.Connection = Depends(get_db),
) -> Dict[str, Any]:
    """
    Resolve an alert once flood waters recede and communities are confirmed safe.
    """
    cursor = await db.execute("SELECT id, status FROM alerts WHERE id = ?", (alert_id,))
    alert = await cursor.fetchone()
    if not alert:
        raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found.")

    now_iso = datetime.now(timezone.utc).isoformat()
    resolver = payload.resolved_by if payload else "Disaster Coordinator"
    notes = payload.resolution_notes if payload else "Water levels normalized below alarm threshold."

    await db.execute(
        """
        UPDATE alerts
        SET status = 'resolved', resolved_at = ?
        WHERE id = ?
        """,
        (now_iso, alert_id),
    )

    await db.execute(
        """
        INSERT INTO audit_log (action, entity_type, entity_id, details_json, performed_by, created_at)
        VALUES ('RESOLVE_ALERT', 'alert', ?, ?, ?, ?)
        """,
        (str(alert_id), json.dumps({"notes": notes}), resolver, now_iso),
    )
    await db.commit()

    broker.publish("alert_changed", {"alert_id": alert_id, "status": "resolved"})

    return {
        "status": "success",
        "alert_id": alert_id,
        "new_status": "resolved",
        "resolved_at": now_iso,
        "resolved_by": resolver,
    }


@router.post("/evaluate")
async def evaluate_live_thresholds(
    db: aiosqlite.Connection = Depends(get_db),
) -> Dict[str, Any]:
    """
    Run live threshold evaluation across all monitoring locations and hydrological stations.
    """
    new_alerts = await alert_service.check_thresholds(db)
    return {
        "status": "completed",
        "new_alerts_generated": len(new_alerts),
        "alerts": new_alerts,
    }


@router.get("/telegram-status")
async def get_telegram_status() -> Dict[str, Any]:
    """
    Return real Telegram bot configuration status without exposing the full token.
    """
    configured = telegram_service.is_configured()
    raw_token = getattr(settings, "TELEGRAM_BOT_TOKEN", "") or ""
    masked_token = (
        f"{raw_token[:12]}*******************" if len(raw_token) > 12 else "Not Configured"
    )
    default_chat_id = str(getattr(settings, "TELEGRAM_CHAT_ID", "") or "")

    return {
        "connected": configured,
        "bot_username": "@TonleSapFloodBot",
        "masked_token": masked_token,
        "default_chat_id": default_chat_id,
    }


@router.post("/test-telegram")
async def send_test_telegram(
    chat_id: Optional[str] = Query(None, description="Optional override chat ID"),
) -> Dict[str, Any]:
    """
    Send an operational connectivity verification test message to the configured Telegram bot channel.
    """
    return await telegram_service.send_test_message(chat_id=chat_id)


@router.get("/templates")
async def get_alert_templates() -> Dict[str, Any]:
    """
    Retrieve bilingual Khmer / English emergency alert templates and response advisories.
    """
    return alert_service.get_templates()