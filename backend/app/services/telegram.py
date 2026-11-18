"""
FloodPulse AI - Telegram Bot & Emergency Dispatch Service
Bilingual (English / Khmer) flood alert notification service for Tonle Sap basin.
"""

import html
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional

import httpx
from app.config import settings

logger = logging.getLogger(__name__)


# Khmer and English bilingual message templates by severity level
ALERT_TEMPLATES = {
    "Very High": {
        "icon": "🔴",
        "tag_en": "CRITICAL EMERGENCY - IMMEDIATE ACTION REQUIRED",
        "tag_km": "អាសន្នធ្ងន់ធ្ងរ - ត្រូវចាត់វិធានការជាបន្ទាន់",
        "action_en": "Evacuate low-lying floodplain communes immediately. Move livestock and valuables to designated safe elevated sites.",
        "action_km": "ជម្លៀសចេញពីតំបន់ទំនាបទឹកលិចជាបន្ទាន់។ ផ្លាស់ទីសត្វពាហនៈ និងទ្រព្យសម្បត្តិទៅកាន់ទីទួលសុវត្ថិភាពដែលបានកំណត់។"
    },
    "High": {
        "icon": "🟠",
        "tag_en": "HIGH FLOOD WARNING",
        "tag_km": "ការព្រមានកម្រិតខ្ពស់អំពីទឹកជំនន់",
        "action_en": "Prepare emergency kits, charge communication devices, and monitor Tonle Sap water levels closely.",
        "action_km": "រៀបចំកញ្ចប់សង្គ្រោះបន្ទាន់ បញ្ចូលថ្មឧបករណ៍ទំនាក់ទំនង និងតាមដានកម្ពស់ទឹកបឹងទន្លេសាបឱ្យបានដិតដល់។"
    },
    "Moderate": {
        "icon": "🟡",
        "tag_en": "FLOOD WATCH & ADVISORY",
        "tag_km": "ការប្រកាសអាសន្ន និងការប្រុងប្រយ័ត្នទឹកជំនន់",
        "action_en": "Agricultural lowlands and riverbank communities should secure equipment and monitor daily river discharge.",
        "action_km": "សហគមន៍កសិកម្មតំបន់ទំនាប និងមាត់ស្ទឹងគួរតែការពារឧបករណ៍ និងតាមដានលំហូរទឹកប្រចាំថ្ងៃ។"
    },
    "Low": {
        "icon": "🟢",
        "tag_en": "NORMAL MONITORING STATUS",
        "tag_km": "ស្ថានភាពតាមដានធម្មតា",
        "action_en": "Hydrological indicators are within safe baseline ranges. Continue routine observation.",
        "action_km": "សូចនាករជលសាស្ត្រស្ថិតក្នុងកម្រិតធម្មតា។ បន្តការសង្កេតជាប្រចាំ។"
    }
}


class TelegramService:
    """
    Handles outbound emergency broadcasts and interactive alerts via Telegram Bot API.
    """

    def __init__(self):
        self.bot_token = settings.TELEGRAM_BOT_TOKEN
        self.default_chat_id = settings.TELEGRAM_CHAT_ID
        self.enabled = bool(settings.TELEGRAM_BOT_TOKEN and settings.TELEGRAM_CHAT_ID)
        self.api_base = f"https://api.telegram.org/bot{self.bot_token}" if self.bot_token else ""

    def is_configured(self) -> bool:
        """Check if Telegram credentials are fully set."""
        return bool(self.bot_token and self.default_chat_id)

    def format_alert_message(
        self,
        alert: Dict[str, Any],
        location_name: Optional[str] = None,
        location_km: Optional[str] = None
    ) -> str:
        """
        Format an emergency alert into a clean, bilingual HTML message suitable for Telegram.
        """
        severity = alert.get("severity", "Moderate")
        template = ALERT_TEMPLATES.get(severity, ALERT_TEMPLATES["Moderate"])

        title_en = alert.get("title", f"Flood Alert - {severity}")
        title_km = alert.get("title_km", "ការជូនដំណឹងអំពីទឹកជំនន់")
        message_en = alert.get("message", "")
        message_km = alert.get("message_km", "")
        province = alert.get("province", location_name or "Tonle Sap Basin")
        created_at = alert.get("created_at", datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"))

        risk_score = alert.get("risk_score")
        score_line = f"\n<b>Risk Probability / ប្រូបាប៊ីលីតេហានិភ័យ:</b> {risk_score:.1f}%" if risk_score is not None else ""

        loc_header = f"📍 <b>Location / ទីតាំង:</b> {html.escape(province)}"
        if location_km and location_km != province:
            loc_header += f" ({html.escape(location_km)})"

        body = (
            f"{template['icon']} <b>[FloodPulse AI] {template['tag_en']}</b>\n"
            f"{template['icon']} <b>{template['tag_km']}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"{loc_header}\n"
            f"<b>Severity / កម្រិត:</b> {severity.upper()}{score_line}\n"
            f"<b>Time / ពេលវេលា:</b> {html.escape(str(created_at))}\n"
            f"━━━━━━━━━━━━━━━━━━━\n\n"
            f"📢 <b>{html.escape(title_en)}</b>\n"
            f"{html.escape(message_en)}\n\n"
            f"🇰🇭 <b>{html.escape(title_km)}</b>\n"
            f"{html.escape(message_km)}\n\n"
            f"⚠️ <b>Recommended Actions / វិធានការណែនាំ:</b>\n"
            f"• EN: {template['action_en']}\n"
            f"• KM: {template['action_km']}\n\n"
            f"🌐 <i>Tonle Sap Flood Early Warning Platform | Mekong River Basin</i>"
        )
        return body

    async def send_message(
        self,
        chat_id: Optional[str] = None,
        message: str = "",
        parse_mode: str = "HTML"
    ) -> Dict[str, Any]:
        """
        Send a raw text or HTML message via the Telegram Bot API.
        """
        target_chat = chat_id or self.default_chat_id
        if not self.bot_token or not target_chat:
            logger.warning("Telegram Bot token or Chat ID is not configured. Skipping dispatch.")
            return {
                "success": False,
                "error": "Telegram credentials not configured",
                "chat_id": target_chat,
                "dispatched": False
            }

        endpoint = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = {
            "chat_id": target_chat,
            "text": message,
            "parse_mode": parse_mode,
            "disable_web_page_preview": True
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(endpoint, json=payload)
                data = response.json()
                if response.status_code == 200 and data.get("ok"):
                    logger.info(f"Telegram notification dispatched successfully to {target_chat}")
                    return {
                        "success": True,
                        "message_id": data.get("result", {}).get("message_id"),
                        "chat_id": target_chat,
                        "dispatched": True
                    }
                else:
                    logger.error(f"Telegram API error {response.status_code}: {data.get('description')}")
                    return {
                        "success": False,
                        "error": data.get("description", "Unknown Telegram API error"),
                        "status_code": response.status_code,
                        "dispatched": False
                    }
        except Exception as e:
            logger.exception(f"Exception during Telegram message dispatch: {e}")
            return {
                "success": False,
                "error": str(e),
                "dispatched": False
            }

    async def send_alert(
        self,
        alert: Dict[str, Any],
        chat_id: Optional[str] = None,
        location_name: Optional[str] = None,
        location_km: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Format and broadcast a high-priority flood alert.
        """
        formatted_text = self.format_alert_message(
            alert=alert,
            location_name=location_name,
            location_km=location_km
        )
        return await self.send_message(chat_id=chat_id, message=formatted_text)

    async def send_test_message(self, chat_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Send an operational connectivity test message.
        """
        test_payload = {
            "severity": "Low",
            "title": "System Connectivity Test - FloodPulse AI",
            "title_km": "ការធ្វើតេស្តប្រព័ន្ធតភ្ជាប់ - FloodPulse AI",
            "message": "Operational test dispatched from Tonle Sap Lake Flood Early Warning Engine. Real-time telemetry connection verified.",
            "message_km": "ការធ្វើតេស្តដំណើរការត្រូវបានផ្ញើចេញពីម៉ាស៊ីនប្រកាសអាសន្នទឹកជំនន់បឹងទន្លេសាប។ ការតភ្ជាប់ទិន្នន័យជាក់ស្តែងត្រូវបានបញ្ជាក់។",
            "province": "Tonle Sap Basin Monitoring Centre",
            "risk_score": 12.5,
            "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        }
        return await self.send_alert(
            alert=test_payload,
            chat_id=chat_id,
            location_name="Phnom Penh Central Hub",
            location_km="មជ្ឈមណ្ឌលកណ្តាលភ្នំពេញ"
        )


telegram_service = TelegramService()
