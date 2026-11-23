
"""
FloodPulse AI - Telegram Bot & Emergency Dispatch Service
Bilingual (English / Khmer) flood alert notification service
for the Tonle Sap basin.
"""

import html
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


# ============================================================
# BILINGUAL ALERT TEMPLATES
# ============================================================

ALERT_TEMPLATES = {
    "Very High": {
        "icon": "🔴",
        "tag_en": "CRITICAL EMERGENCY - IMMEDIATE ACTION REQUIRED",
        "tag_km": "អាសន្នធ្ងន់ធ្ងរ - ត្រូវចាត់វិធានការជាបន្ទាន់",
        "action_en": (
            "Evacuate low-lying floodplain communes immediately. "
            "Move livestock and valuables to designated safe elevated sites."
        ),
        "action_km": (
            "ជម្លៀសចេញពីតំបន់ទំនាបទឹកលិចជាបន្ទាន់។ "
            "ផ្លាស់ទីសត្វពាហនៈ និងទ្រព្យសម្បត្តិទៅកាន់ទីទួលសុវត្ថិភាព។"
        ),
    },
    "High": {
        "icon": "🟠",
        "tag_en": "HIGH FLOOD WARNING",
        "tag_km": "ការព្រមានកម្រិតខ្ពស់អំពីទឹកជំនន់",
        "action_en": (
            "Prepare emergency kits, charge communication devices, "
            "and monitor Tonle Sap water levels closely."
        ),
        "action_km": (
            "រៀបចំកញ្ចប់សង្គ្រោះបន្ទាន់ បញ្ចូលថ្មឧបករណ៍ទំនាក់ទំនង "
            "និងតាមដានកម្ពស់ទឹកបឹងទន្លេសាបឱ្យបានដិតដល់។"
        ),
    },
    "Moderate": {
        "icon": "🟡",
        "tag_en": "FLOOD WATCH & ADVISORY",
        "tag_km": "ការប្រកាសអាសន្ន និងការប្រុងប្រយ័ត្នទឹកជំនន់",
        "action_en": (
            "Agricultural lowlands and riverbank communities should "
            "secure equipment and monitor daily river discharge."
        ),
        "action_km": (
            "សហគមន៍កសិកម្មតំបន់ទំនាប និងមាត់ស្ទឹងគួរតែការពារឧបករណ៍ "
            "និងតាមដានលំហូរទឹកប្រចាំថ្ងៃ។"
        ),
    },
    "Low": {
        "icon": "🟢",
        "tag_en": "NORMAL MONITORING STATUS",
        "tag_km": "ស្ថានភាពតាមដានធម្មតា",
        "action_en": (
            "Hydrological indicators are within safe baseline ranges. "
            "Continue routine observation."
        ),
        "action_km": (
            "សូចនាករជលសាស្ត្រស្ថិតក្នុងកម្រិតធម្មតា។ "
            "បន្តការសង្កេតជាប្រចាំ។"
        ),
    },
}


class TelegramService:
    """
    Handles outbound Telegram notifications and emergency broadcasts.
    """

    def __init__(self):
        self.bot_token = settings.TELEGRAM_BOT_TOKEN
        self.default_chat_id = settings.TELEGRAM_CHAT_ID

        self.bot_enabled = bool(
            self.bot_token and settings.TELEGRAM_BOT_ENABLED
        )

        self.alerts_enabled = bool(
            self.bot_enabled
            and self.default_chat_id
            and settings.TELEGRAM_ALERTS_ENABLED
        )

        self.api_base = (
            f"https://api.telegram.org/bot{self.bot_token}"
            if self.bot_token
            else ""
        )

    # ========================================================
    # CONFIGURATION
    # ========================================================

    def is_configured(self) -> bool:
        """Check whether Telegram credentials are available."""
        return bool(self.bot_token and self.default_chat_id)

    def is_enabled(self) -> bool:
        """Check whether the Telegram bot is enabled."""
        return self.bot_enabled

    def are_alerts_enabled(self) -> bool:
        """Check whether automatic alert dispatch is enabled."""
        return self.alerts_enabled

    # ========================================================
    # MESSAGE FORMATTING
    # ========================================================

    def format_alert_message(
        self,
        alert: Dict[str, Any],
        location_name: Optional[str] = None,
        location_km: Optional[str] = None,
    ) -> str:
        """Create a bilingual HTML-formatted flood alert."""

        severity = str(alert.get("severity", "Moderate"))

        template = ALERT_TEMPLATES.get(
            severity,
            ALERT_TEMPLATES["Moderate"],
        )

        title_en = html.escape(
            str(alert.get("title", f"Flood Alert - {severity}"))
        )

        title_km = html.escape(
            str(alert.get("title_km", "ការជូនដំណឹងអំពីទឹកជំនន់"))
        )

        message_en = html.escape(str(alert.get("message", "")))
        message_km = html.escape(str(alert.get("message_km", "")))

        province = str(
            alert.get("province")
            or location_name
            or "Tonle Sap Basin"
        )

        created_at = str(
            alert.get(
                "created_at",
                datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            )
        )

        risk_score = alert.get("risk_score")

        score_line = ""

        if risk_score is not None:
            try:
                score = float(risk_score)
                score_line = (
                    f"\n<b>Risk Probability / "
                    f"ប្រូបាប៊ីលីតេហានិភ័យ:</b> {score:.1f}%"
                )
            except (TypeError, ValueError):
                logger.warning("Invalid risk score: %s", risk_score)

        loc_header = (
            f"📍 <b>Location / ទីតាំង:</b> "
            f"{html.escape(province)}"
        )

        if location_km and location_km != province:
            loc_header += f" ({html.escape(location_km)})"

        body = (
            f"{template['icon']} "
            f"<b>[FloodPulse AI] {template['tag_en']}</b>\n"
            f"{template['icon']} "
            f"<b>{template['tag_km']}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"{loc_header}\n"
            f"<b>Severity / កម្រិត:</b> "
            f"{html.escape(severity.upper())}"
            f"{score_line}\n"
            f"<b>Time / ពេលវេលា:</b> "
            f"{html.escape(created_at)}\n"
            f"━━━━━━━━━━━━━━━━━━━\n\n"
            f"📢 <b>{title_en}</b>\n"
            f"{message_en}\n\n"
            f"🇰🇭 <b>{title_km}</b>\n"
            f"{message_km}\n\n"
            f"⚠️ <b>Recommended Actions / "
            f"វិធានការណែនាំ:</b>\n"
            f"• EN: {template['action_en']}\n"
            f"• KM: {template['action_km']}\n\n"
            f"🌐 <i>Tonle Sap Flood Early Warning Platform "
            f"| Mekong River Basin</i>"
        )

        return body

    # ========================================================
    # SEND MESSAGE
    # ========================================================

    async def send_message(
        self,
        chat_id: Optional[str] = None,
        message: str = "",
        parse_mode: str = "HTML",
    ) -> Dict[str, Any]:
        """Send a Telegram message."""

        target_chat = chat_id or self.default_chat_id

        if not self.bot_enabled:
            return {
                "success": False,
                "error": "Telegram bot is disabled",
                "dispatched": False,
            }

        if not target_chat:
            return {
                "success": False,
                "error": "Telegram Chat ID is not configured",
                "dispatched": False,
            }

        if not self.bot_token:
            return {
                "success": False,
                "error": "Telegram Bot Token is not configured",
                "dispatched": False,
            }

        endpoint = f"{self.api_base}/sendMessage"

        payload = {
            "chat_id": target_chat,
            "text": message,
            "parse_mode": parse_mode,
            "disable_web_page_preview": True,
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(
                    endpoint,
                    json=payload,
                )

                data = response.json()

                if response.status_code == 200 and data.get("ok"):
                    message_id = data.get("result", {}).get("message_id")

                    logger.info(
                        "Telegram notification sent to chat %s",
                        target_chat,
                    )

                    return {
                        "success": True,
                        "message_id": message_id,
                        "chat_id": target_chat,
                        "dispatched": True,
                    }

                error_message = data.get(
                    "description",
                    "Unknown Telegram API error",
                )

                logger.error(
                    "Telegram API error %s: %s",
                    response.status_code,
                    error_message,
                )

                return {
                    "success": False,
                    "error": error_message,
                    "status_code": response.status_code,
                    "dispatched": False,
                }

        except httpx.TimeoutException:
            logger.exception("Telegram request timed out")

            return {
                "success": False,
                "error": "Telegram request timed out",
                "dispatched": False,
            }

        except Exception as exc:
            logger.exception(
                "Telegram message dispatch failed: %s",
                exc,
            )

            return {
                "success": False,
                "error": str(exc),
                "dispatched": False,
            }

    # ========================================================
    # SEND FLOOD ALERT
    # ========================================================

    async def send_alert(
        self,
        alert: Dict[str, Any],
        chat_id: Optional[str] = None,
        location_name: Optional[str] = None,
        location_km: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Send a bilingual flood alert if alerts are enabled."""

        if not self.alerts_enabled:
            logger.info(
                "Telegram flood alerts are disabled. "
                "Skipping alert dispatch."
            )

            return {
                "success": False,
                "error": "Telegram alerts are disabled",
                "dispatched": False,
            }

        formatted_text = self.format_alert_message(
            alert=alert,
            location_name=location_name,
            location_km=location_km,
        )

        return await self.send_message(
            chat_id=chat_id,
            message=formatted_text,
        )

    # ========================================================
    # TEST MESSAGE
    # ========================================================

    async def send_test_message(
        self,
        chat_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Send a test notification to verify Telegram connectivity."""

        test_payload = {
            "severity": "Low",
            "title": "System Connectivity Test - FloodPulse AI",
            "title_km": "ការធ្វើតេស្តប្រព័ន្ធតភ្ជាប់ - FloodPulse AI",
            "message": (
                "Operational test dispatched from the Tonle Sap "
                "Flood Early Warning Engine."
            ),
            "message_km": (
                "ការធ្វើតេស្តដំណើរការត្រូវបានផ្ញើចេញពីប្រព័ន្ធ "
                "ប្រកាសអាសន្នទឹកជំនន់បឹងទន្លេសាប។"
            ),
            "province": "Tonle Sap Basin Monitoring Centre",
            "risk_score": 12.5,
            "created_at": datetime.now(timezone.utc).strftime(
                "%Y-%m-%d %H:%M:%S UTC"
            ),
        }

        formatted_text = self.format_alert_message(
            alert=test_payload,
            location_name="Phnom Penh Central Hub",
            location_km="មជ្ឈមណ្ឌលកណ្តាលភ្នំពេញ",
        )

        # Connectivity test is allowed when the bot is enabled,
        # even if automatic flood alerts are disabled.
        return await self.send_message(
            chat_id=chat_id,
            message=formatted_text,
        )


# ============================================================
# GLOBAL SERVICE INSTANCE
# ============================================================

telegram_service = TelegramService()
