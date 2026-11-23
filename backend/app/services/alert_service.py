"""
FloodPulse AI - Alert Generation & Threshold Verification Service
Monitors hydrological and risk thresholds, generates database alerts, and coordinates Telegram dispatches.
"""

import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional

import aiosqlite
from app.config import settings
from app.services.telegram import telegram_service
from app.services.risk_engine import risk_engine
from app.services.realtime import broker

logger = logging.getLogger(__name__)


# Alert message bilingual templates
ALERT_TEMPLATES = {
    "Very High": {
        "title_en": "CRITICAL EMERGENCY: Extreme Flood Danger",
        "title_km": "ការប្រកាសអាសន្នបន្ទាន់៖ គ្រោះថ្នាក់ទឹកជំនន់ធ្ងន់ធ្ងរបំផុត",
        "msg_template_en": "Flood risk has reached critical levels ({probability:.1f}%) in {location_name}, {province}. Major inundation of residential and agricultural lands is occurring or imminent.",
        "msg_template_km": "កម្រិតហានិភ័យទឹកជំនន់បានឡើងដល់កម្រិតធ្ងន់ធ្ងរ ({probability:.1f}%) នៅ{location_name_km} ខេត្ត{province}។ ការលិចលង់ធ្ងន់ធ្ងរលើតំបន់លំនៅដ្ឋាន និងដីកសិកម្មកំពុងកើតឡើង ឬជិតកើតមាន។",
    },
    "High": {
        "title_en": "HIGH WARNING: Severe Inundation Threat",
        "title_km": "ការព្រមានកម្រិតខ្ពស់៖ ការគំរាមកំហែងពីទឹកជំនន់ខ្លាំង",
        "msg_template_en": "Elevated flood risk of {probability:.1f}% detected in {location_name}, {province}. Tributaries and Tonle Sap lake margins are swelling rapidly.",
        "msg_template_km": "ហានិភ័យទឹកជំនន់កម្រិតខ្ពស់ {probability:.1f}% ត្រូវបានរកឃើញនៅ{location_name_km} ខេត្ត{province}។ ដៃទន្លេ និងមាត់បឹងទន្លេសាបកំពុងហក់ឡើងយ៉ាងលឿន។",
    },
    "Moderate": {
        "title_en": "FLOOD ADVISORY: Heightened Water Levels",
        "title_km": "សេចក្តីជូនដំណឹងអំពីទឹកជំនន់៖ កម្ពស់ទឹកកើនឡើង",
        "msg_template_en": "Moderate flood advisory ({probability:.1f}%) for {location_name}, {province}. Soil saturation is high and water levels are approaching warning thresholds.",
        "msg_template_km": "ការជូនដំណឹងអំពីទឹកជំនន់កម្រិតមធ្យម ({probability:.1f}%) សម្រាប់{location_name_km} ខេត្ត{province}។ ដីមានសំណើមខ្ពស់ ហើយកម្ពស់ទឹកជិតដល់កម្រិតប្រកាសអាសន្ន។",
    },
    "Low": {
        "title_en": "MONITORING STATUS: Baseline Hydrology",
        "title_km": "ស្ថានភាពតាមដាន៖ ជលសាស្ត្រធម្មតា",
        "msg_template_en": "Hydrological indicators for {location_name}, {province} remain within seasonal baseline parameters ({probability:.1f}%).",
        "msg_template_km": "សូចនាករជលសាស្ត្រសម្រាប់{location_name_km} ខេត្ត{province} នៅតែស្ថិតក្នុងកម្រិតធម្មតាតាមរដូវកាល ({probability:.1f}%)។",
    }
}


class AlertService:
    """
    Manages flood threshold triggers, alert deduplication, and multichannel broadcasting.
    """

    def __init__(self):
        self.telegram = telegram_service

    def get_templates(self) -> Dict[str, Any]:
        """Return available bilingual alert templates."""
        return ALERT_TEMPLATES

    def format_telegram_message(
        self,
        alert: Dict[str, Any],
        location_info: Optional[Dict[str, Any]] = None
    ) -> str:
        """Format an alert specifically for Telegram delivery."""
        loc_name = location_info.get("name") if location_info else alert.get("province")
        loc_km = location_info.get("name_km") if location_info else None
        return self.telegram.format_alert_message(
            alert=alert,
            location_name=loc_name,
            location_km=loc_km
        )

    async def generate_alert(
        self,
        db: aiosqlite.Connection,
        location_id: int,
        severity: str,
        probability: float,
        location_name: str,
        location_name_km: str,
        province: str,
        trigger_source: str = "RiskEngine",
        trigger_data: Optional[Dict[str, Any]] = None,
        force: bool = False
    ) -> Optional[Dict[str, Any]]:
        """
        Create a new alert record in the database if not recently notified (deduplication within 12h).
        """
        now = datetime.now(timezone.utc)
        twelve_hours_ago = (now - timedelta(hours=12)).isoformat()

        # Check for active alert to avoid alert fatigue
        if not force:
            cursor = await db.execute(
                """
                SELECT id, severity, created_at FROM alerts 
                WHERE location_id = ? AND status = 'active' AND severity = ? AND created_at >= ?
                ORDER BY created_at DESC LIMIT 1
                """,
                (location_id, severity, twelve_hours_ago)
            )
            existing = await cursor.fetchone()
            if existing:
                logger.info(f"Suppressed duplicate {severity} alert for location {location_id} (active alert {existing['id']} exists)")
                return None

        template = ALERT_TEMPLATES.get(severity, ALERT_TEMPLATES["Moderate"])
        title_en = template["title_en"]
        title_km = template["title_km"]
        message_en = template["msg_template_en"].format(
            probability=probability,
            location_name=location_name,
            province=province
        )
        message_km = template["msg_template_km"].format(
            probability=probability,
            location_name_km=location_name_km or location_name,
            province=province
        )

        alert_type = "FLOOD_EARLY_WARNING"
        trigger_json = json.dumps(trigger_data or {})

        cursor = await db.execute(
            """
            INSERT INTO alerts (
                alert_type, severity, title, title_km, message, message_km,
                location_id, province, trigger_source, trigger_data_json,
                status, telegram_sent, created_at, created_by
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', 0, ?, 'system')
            """,
            (
                alert_type, severity, title_en, title_km, message_en, message_km,
                location_id, province, trigger_source, trigger_json, now.isoformat()
            )
        )
        alert_id = cursor.lastrowid
        await db.commit()

        alert_record = {
            "id": alert_id,
            "alert_type": alert_type,
            "severity": severity,
            "title": title_en,
            "title_km": title_km,
            "message": message_en,
            "message_km": message_km,
            "location_id": location_id,
            "province": province,
            "risk_score": probability,
            "status": "active",
            "created_at": now.isoformat()
        }

        # Attempt Telegram dispatch if configured
        if self.telegram.is_configured():
            try:
                tg_res = await self.telegram.send_alert(
                    alert=alert_record,
                    location_name=location_name,
                    location_km=location_name_km
                )
                if tg_res.get("success"):
                    msg_id = str(tg_res.get("message_id", ""))
                    await db.execute(
                        "UPDATE alerts SET telegram_sent = 1, telegram_message_id = ? WHERE id = ?",
                        (msg_id, alert_id)
                    )
                    await db.commit()
                    alert_record["telegram_sent"] = 1
            except Exception as e:
                logger.error(f"Failed to dispatch Telegram alert for alert {alert_id}: {e}")

        try:
            broker.publish(
                "alert_created",
                {
                    "alert_id": alert_id,
                    "severity": severity,
                    "province": province,
                    "title": title_en,
                },
            )
        except Exception:
            logger.exception("Could not publish alert_created event.")

        return alert_record

    async def check_thresholds(self, db: aiosqlite.Connection) -> List[Dict[str, Any]]:
        """
        Evaluate all monitored locations and stations against safety thresholds.
        Automatically raises High/Very High alerts.
        """
        new_alerts = []
        now = datetime.now(timezone.utc)

        # 1. Evaluate risk assessment categories
        cursor = await db.execute("SELECT id, name, name_km, province FROM monitoring_locations")
        locations = await cursor.fetchall()

        for loc in locations:
            loc_id = loc["id"]
            assessment = await risk_engine.assess_location(loc_id, db)
            category = assessment.get("risk_category")
            prob = assessment.get("risk_probability", 0.0)

            # High or Very High triggers emergency alert
            if category in ("High", "Very High"):
                alert = await self.generate_alert(
                    db=db,
                    location_id=loc_id,
                    severity=category,
                    probability=prob,
                    location_name=loc["name"],
                    location_name_km=loc["name_km"],
                    province=loc["province"],
                    trigger_source="RiskAssessmentEngine",
                    trigger_data=assessment
                )
                if alert:
                    new_alerts.append(alert)

        # 2. Check hydrological station gauge alarms directly
        st_cursor = await db.execute(
            """
            SELECT s.id, s.name, s.name_km, s.province, s.alarm_level, s.flood_level, wl.value as water_level
            FROM stations s
            JOIN water_levels wl ON s.id = wl.station_id
            WHERE s.is_active = 1
            AND wl.id = (
                SELECT id FROM water_levels 
                WHERE station_id = s.id 
                ORDER BY timestamp DESC LIMIT 1
            )
            """
        )
        stations = await st_cursor.fetchall()

        for st in stations:
            wl = st["water_level"]
            alarm = st["alarm_level"]
            flood = st["flood_level"]

            if flood and wl >= flood:
                # Water level breached flood level
                alert = await self.generate_alert(
                    db=db,
                    location_id=st["id"],
                    severity="Very High",
                    probability=95.0,
                    location_name=st["name"],
                    location_name_km=st["name_km"],
                    province=st["province"],
                    trigger_source="HydrologicalStationAlarm",
                    trigger_data={"water_level": wl, "flood_level": flood, "station": st["name"]},
                    force=False
                )
                if alert:
                    new_alerts.append(alert)
            elif alarm and wl >= alarm:
                # Water level breached alarm level
                alert = await self.generate_alert(
                    db=db,
                    location_id=st["id"],
                    severity="High",
                    probability=78.0,
                    location_name=st["name"],
                    location_name_km=st["name_km"],
                    province=st["province"],
                    trigger_source="HydrologicalStationWarning",
                    trigger_data={"water_level": wl, "alarm_level": alarm, "station": st["name"]},
                    force=False
                )
                if alert:
                    new_alerts.append(alert)

        return new_alerts


alert_service = AlertService()