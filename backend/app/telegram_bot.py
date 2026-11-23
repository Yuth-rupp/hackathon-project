"""
FloodPulse AI - Intelligent Telegram Assistant
Cambodia weather intelligence and Tonle Sap flood awareness.

Features:
- Interactive Telegram commands
- Natural-language intent recognition
- English and basic Khmer keyword support
- Cambodian province recognition
- Live weather and forecast through Open-Meteo
- Live flood-alert queries from floodpulse.db
- Safe error handling
"""

import logging
import re
from typing import Optional, Dict, Any

import aiosqlite
import httpx

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from app.config import settings


logger = logging.getLogger("floodpulse.telegram")

# ============================================================
# CONFIGURATION
# ============================================================

WEATHER_GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
WEATHER_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
HTTP_TIMEOUT = 15.0
DEFAULT_LOCATION = "Phnom Penh"

CAMBODIA_LOCATIONS = {
    "phnom penh": "Phnom Penh",
    "phnompenh": "Phnom Penh",
    "ភ្នំពេញ": "Phnom Penh",
    "battambang": "Battambang",
    "batdambang": "Battambang",
    "បាត់ដំបង": "Battambang",
    "siem reap": "Siem Reap",
    "siemreap": "Siem Reap",
    "សៀមរាប": "Siem Reap",
    "kampong thom": "Kampong Thom",
    "kompong thom": "Kampong Thom",
    "កំពង់ធំ": "Kampong Thom",
    "pursat": "Pursat",
    "ពោធិ៍សាត់": "Pursat",
    "kampong cham": "Kampong Cham",
    "កំពង់ចាម": "Kampong Cham",
    "kampong chhnang": "Kampong Chhnang",
    "កំពង់ឆ្នាំង": "Kampong Chhnang",
    "kampong speu": "Kampong Speu",
    "កំពង់ស្ពឺ": "Kampong Speu",
    "prey veng": "Prey Veng",
    "ព្រៃវែង": "Prey Veng",
    "svay rieng": "Svay Rieng",
    "ស្វាយរៀង": "Svay Rieng",
    "takeo": "Takeo",
    "តាកែវ": "Takeo",
    "kandal": "Kandal",
    "កណ្តាល": "Kandal",
    "kratie": "Kratie",
    "ក្រចេះ": "Kratie",
    "stung treng": "Stung Treng",
    "ស្ទឹងត្រែង": "Stung Treng",
    "preah vihear": "Preah Vihear",
    "ព្រះវិហារ": "Preah Vihear",
    "oddar meanchey": "Oddar Meanchey",
    "ឧត្តរមានជ័យ": "Oddar Meanchey",
    "banteay meanchey": "Banteay Meanchey",
    "បន្ទាយមានជ័យ": "Banteay Meanchey",
    "kampot": "Kampot",
    "កំពត": "Kampot",
    "kep": "Kep",
    "កែប": "Kep",
    "koh kong": "Koh Kong",
    "កោះកុង": "Koh Kong",
    "mondulkiri": "Mondulkiri",
    "មណ្ឌលគិរី": "Mondulkiri",
    "ratanakiri": "Ratanakiri",
    "រតនគិរី": "Ratanakiri",
    "pailin": "Pailin",
    "ប៉ៃលិន": "Pailin",
    "preah sihanouk": "Sihanoukville",
    "sihanoukville": "Sihanoukville",
    "ព្រះសីហនុ": "Sihanoukville",
    "tbong khmum": "Tbong Khmum",
    "ត្បូងឃ្មុំ": "Tbong Khmum",
}


# ============================================================
# INTENT RECOGNITION
# ============================================================

WEATHER_KEYWORDS = (
    "weather",
    "temperature",
    "forecast",
    "rain",
    "rainfall",
    "raining",
    "hot",
    "cold",
    "wind",
    "humidity",
    "precipitation",
    "sunny",
    "cloudy",
    "storm",
    "ភ្លៀង",
    "អាកាសធាតុ",
    "សីតុណ្ហភាព",
    "ក្តៅ",
    "ត្រជាក់",
    "ខ្យល់",
)

FLOOD_KEYWORDS = (
    "flood",
    "flooding",
    "flood risk",
    "water level",
    "river level",
    "river overflow",
    "inundation",
    "tonle sap",
    "flood warning",
    "water rising",
    "ទឹកជំនន់",
    "ទឹកឡើង",
    "កម្ពស់ទឹក",
    "បឹងទន្លេសាប",
    "ជំនន់",
)

GREETING_KEYWORDS = {
    "hello",
    "hi",
    "hey",
    "hello there",
    "good morning",
    "good afternoon",
    "good evening",
    "good night",
    "សួស្តី",
    "ជំរាបសួរ",
}

THANKS_KEYWORDS = {
    "thanks",
    "thank you",
    "thank",
    "thank you very much",
    "អរគុណ",
    "អរគុណច្រើន",
}


def detect_intent(message: str) -> str:
    text = message.lower().strip()
    if text in GREETING_KEYWORDS:
        return "greeting"
    if text in THANKS_KEYWORDS:
        return "thanks"
    if any(word in text for word in WEATHER_KEYWORDS):
        return "weather"
    if any(word in text for word in FLOOD_KEYWORDS):
        return "flood"
    return "general"


def extract_location(message: str) -> Optional[str]:
    text = message.lower()
    locations = sorted(
        CAMBODIA_LOCATIONS.items(),
        key=lambda item: len(item[0]),
        reverse=True,
    )
    for alias, location in locations:
        if alias.isascii():
            pattern = r"(?<![a-z])" + re.escape(alias) + r"(?![a-z])"
            if re.search(pattern, text):
                return location
        elif alias in text:
            return location
    return None


def is_tomorrow_request(message: str) -> bool:
    text = message.lower()
    return any(word in text for word in ("tomorrow", "ថ្ងៃស្អែក"))


def is_today_request(message: str) -> bool:
    text = message.lower()
    return any(
        word in text
        for word in ("today", "now", "current", "right now", "ថ្ងៃនេះ", "ឥឡូវនេះ")
    )


# ============================================================
# WEATHER SERVICE
# ============================================================

async def geocode_location(location: str) -> Optional[Dict[str, Any]]:
    params = {
        "name": location,
        "count": 5,
        "language": "en",
        "format": "json",
        "countryCode": "KH",
    }
    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
        response = await client.get(WEATHER_GEOCODING_URL, params=params)
        response.raise_for_status()
        data = response.json()

    results = data.get("results", [])
    if not results:
        return None
    for result in results:
        if result.get("country_code") == "KH":
            return result
    return results[0]


def describe_weather(code: Optional[int]) -> str:
    descriptions = {
        0: "Clear sky",
        1: "Mainly clear",
        2: "Partly cloudy",
        3: "Overcast",
        45: "Fog",
        48: "Depositing rime fog",
        51: "Light drizzle",
        53: "Moderate drizzle",
        55: "Dense drizzle",
        56: "Freezing drizzle",
        57: "Heavy freezing drizzle",
        61: "Slight rain",
        63: "Moderate rain",
        65: "Heavy rain",
        66: "Freezing rain",
        67: "Heavy freezing rain",
        71: "Slight snowfall",
        73: "Moderate snowfall",
        75: "Heavy snowfall",
        77: "Snow grains",
        80: "Rain showers",
        81: "Moderate rain showers",
        82: "Violent rain showers",
        85: "Snow showers",
        86: "Heavy snow showers",
        95: "Thunderstorm",
        96: "Thunderstorm with hail",
        99: "Severe thunderstorm with hail",
    }
    if code is None:
        return "Unavailable"
    return descriptions.get(int(code), "Unknown weather conditions")


async def get_weather(location: str, tomorrow: bool = False) -> str:
    try:
        place = await geocode_location(location)
        if not place:
            return (
                f"❌ I couldn't find '{location}' in Cambodia.\n\n"
                "Please provide a Cambodian city or province."
            )

        latitude = place["latitude"]
        longitude = place["longitude"]
        display_name = place.get("name", location)
        admin = place.get("admin1", "")

        params = {
            "latitude": latitude,
            "longitude": longitude,
            "current": (
                "temperature_2m,"
                "relative_humidity_2m,"
                "apparent_temperature,"
                "precipitation,"
                "rain,"
                "showers,"
                "weather_code,"
                "wind_speed_10m"
            ),
            "daily": (
                "weather_code,"
                "temperature_2m_max,"
                "temperature_2m_min,"
                "precipitation_sum,"
                "precipitation_probability_max"
            ),
            "timezone": "auto",
            "forecast_days": 2,
        }

        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            response = await client.get(WEATHER_FORECAST_URL, params=params)
            response.raise_for_status()
            data = response.json()

        current = data.get("current", {})
        daily = data.get("daily", {})

        if not current or not daily:
            return "⚠️ Weather information is temporarily unavailable. Please try again later."

        index = 1 if tomorrow else 0
        dates = daily.get("time", [])
        if len(dates) <= index:
            return "⚠️ The requested forecast is unavailable."

        date = dates[index]
        code = daily.get("weather_code", [None])[index]
        maximum = daily.get("temperature_2m_max", [None])[index]
        minimum = daily.get("temperature_2m_min", [None])[index]
        rainfall = daily.get("precipitation_sum", [None])[index]
        rain_probability = daily.get("precipitation_probability_max", [None])[index]

        if tomorrow:
            return (
                f"🌦️ FLOODPULSE AI - WEATHER FORECAST\n\n"
                f"📍 Location: {display_name}, {admin}\n"
                f"📅 Date: {date}\n\n"
                f"🌤️ Conditions: {describe_weather(code)}\n"
                f"🌡️ Maximum temperature: {maximum}°C\n"
                f"🌡️ Minimum temperature: {minimum}°C\n"
                f"🌧️ Expected rainfall: {rainfall} mm\n"
                f"☔ Rain probability: {rain_probability}%\n\n"
                "Stay informed and monitor local weather conditions.\n\n"
                "Source: Open-Meteo"
            )

        temperature = current.get("temperature_2m")
        feels_like = current.get("apparent_temperature")
        humidity = current.get("relative_humidity_2m")
        wind = current.get("wind_speed_10m")
        current_rain = current.get("rain")
        current_precipitation = current.get("precipitation")
        current_code = current.get("weather_code")

        return (
            f"🌦️ FLOODPULSE AI - CURRENT WEATHER\n\n"
            f"📍 Location: {display_name}, {admin}\n\n"
            f"🌤️ Conditions: {describe_weather(current_code)}\n"
            f"🌡️ Temperature: {temperature}°C\n"
            f"🌡️ Feels like: {feels_like}°C\n"
            f"💧 Humidity: {humidity}%\n"
            f"🌧️ Current rainfall: {current_rain} mm\n"
            f"🌧️ Precipitation: {current_precipitation} mm\n"
            f"💨 Wind speed: {wind} km/h\n\n"
            f"📅 Today's forecast:\n"
            f"Maximum: {maximum}°C\n"
            f"Minimum: {minimum}°C\n"
            f"Expected rainfall: {rainfall} mm\n"
            f"Rain probability: {rain_probability}%\n\n"
            "Source: Open-Meteo"
        )

    except httpx.TimeoutException:
        logger.warning("Weather request timed out for %s", location)
        return "⏳ Weather service is taking too long to respond.\nPlease try again shortly."
    except httpx.HTTPStatusError as exc:
        logger.error("Weather API HTTP error: %s", exc)
        return "⚠️ Weather service is temporarily unavailable.\nPlease try again later."
    except Exception:
        logger.exception("Weather request failed for %s", location)
        return "⚠️ I couldn't retrieve weather information.\nPlease try again later."


# ============================================================
# LIVE FLOOD INFORMATION
# ============================================================

async def get_flood_response(location: Optional[str] = None) -> str:
    """
    Query live active flood warnings from floodpulse.db.
    """
    place = location or "Tonle Sap Basin"
    db_path = getattr(settings, "DATABASE_PATH", "floodpulse.db")

    try:
        async with aiosqlite.connect(db_path) as db:
            db.row_factory = aiosqlite.Row
            if location:
                cursor = await db.execute(
                    """
                    SELECT severity, title, province, message, created_at
                    FROM alerts
                    WHERE status = 'active' AND LOWER(province) LIKE LOWER(?)
                    ORDER BY id DESC LIMIT 3
                    """,
                    (f"%{location}%",),
                )
            else:
                cursor = await db.execute(
                    """
                    SELECT severity, title, province, message, created_at
                    FROM alerts
                    WHERE status = 'active'
                    ORDER BY id DESC LIMIT 5
                    """
                )
            rows = await cursor.fetchall()

        if not rows:
            return (
                f"🌊 FLOODPULSE AI - LIVE STATUS\n\n"
                f"📍 Location: {place}\n"
                f"✅ No active flood warnings at this time.\n\n"
                "Monitoring continues 24/7. Always cross-reference with official MOWRAM & NCDM bulletins."
            )

        lines = [f"🚨 FLOODPULSE AI - ACTIVE WARNINGS ({place})"]
        for r in rows:
            lines.append(
                f"• [{r['severity'].upper()}] {r['province']}: {r['title']}\n"
                f"  {r['message']}"
            )
        lines.append("⚠️ Dial 1294 in Cambodia for official NCDM emergency alerts & rescue.")
        return "\n\n".join(lines)

    except Exception as exc:
        logger.error("Failed to query live flood alerts: %s", exc)
        return (
            "⚠️ Unable to fetch live flood alerts right now.\n"
            "Please check the FloodPulse AI dashboard or official MOWRAM / NCDM broadcasts."
        )


# ============================================================
# TELEGRAM COMMAND HANDLERS
# ============================================================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    await update.message.reply_text(
        "🌊 Welcome to FloodPulse AI!\n\n"
        "Your intelligent Cambodia weather and flood monitoring assistant.\n\n"
        "You can ask me questions naturally, for example:\n\n"
        "🌤️ What's the weather in Battambang?\n"
        "🌧️ Will it rain tomorrow in Phnom Penh?\n"
        "🌊 What is the flood risk around Tonle Sap?\n"
        "📍 Show me weather in Siem Reap.\n\n"
        "I support English and basic Khmer questions.\n\n"
        "Type /help to see available commands."
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    await update.message.reply_text(
        "🌊 FLOODPULSE AI - HELP CENTER\n\n"
        "WEATHER COMMANDS\n"
        "/weather - Weather in Phnom Penh\n"
        "/weather Battambang\n"
        "/weather Siem Reap\n\n"
        "FLOOD COMMANDS\n"
        "/flood - Tonle Sap live flood alerts\n"
        "/flood Battambang\n\n"
        "NATURAL QUESTIONS\n"
        "• What's the weather today?\n"
        "• Will it rain tomorrow in Battambang?\n"
        "• Is it hot in Phnom Penh?\n"
        "• What is the flood risk in Siem Reap?\n"
        "• តើថ្ងៃស្អែកមានភ្លៀងទេ?\n"
        "• តើមានទឹកជំនន់ទេ?\n\n"
        "OTHER COMMANDS\n"
        "/start - Start the assistant\n"
        "/help - Show this help message\n\n"
        "🌍 Monitoring Cambodia and the Tonle Sap Basin."
    )


async def weather_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    location = " ".join(context.args).strip() if context.args else DEFAULT_LOCATION
    await update.message.chat.send_action(ChatAction.TYPING)
    result = await get_weather(location=location, tomorrow=False)
    await update.message.reply_text(result)


async def flood_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    location = " ".join(context.args).strip() if context.args else None
    await update.message.chat.send_action(ChatAction.TYPING)
    result = await get_flood_response(location)
    await update.message.reply_text(result)


# ============================================================
# NATURAL LANGUAGE MESSAGE HANDLER
# ============================================================

async def text_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    original_message = update.message.text.strip()
    message = original_message.lower()
    if not message:
        return

    intent = detect_intent(message)
    location = extract_location(original_message)

    await update.message.chat.send_action(ChatAction.TYPING)

    if intent == "greeting":
        await update.message.reply_text(
            "🌊 Hello! Welcome to FloodPulse AI.\n\n"
            "I can help you understand weather and flood monitoring information across Cambodia.\n\n"
            "Try asking:\n"
            "• What's the weather in Battambang?\n"
            "• Will it rain tomorrow?\n"
            "• What is the flood risk around Tonle Sap?\n\n"
            "How can I help you today?"
        )
        return

    if intent == "thanks":
        await update.message.reply_text(
            "You're welcome! 😊\n\n"
            "FloodPulse AI is here to help communities stay informed and prepared.\n\n"
            "Stay safe!"
        )
        return

    if intent == "weather":
        selected_location = location or DEFAULT_LOCATION
        tomorrow = is_tomorrow_request(message)
        result = await get_weather(location=selected_location, tomorrow=tomorrow)
        await update.message.reply_text(result)
        return

    if intent == "flood":
        result = await get_flood_response(location)
        await update.message.reply_text(result)
        return

    await update.message.reply_text(
        "🌊 Thank you for contacting FloodPulse AI!\n\n"
        "I can currently help with:\n\n"
        "🌤️ Weather information\n"
        "🌧️ Rainfall forecasts\n"
        "🌊 Live flood alerts\n"
        "📍 Cambodian locations\n\n"
        "For example, try:\n"
        "• What's the weather in Battambang?\n"
        "• Will it rain tomorrow in Phnom Penh?\n"
        "• What is the flood risk around Tonle Sap?\n\n"
        "I couldn't confidently identify your question.\n"
        "Please try asking in another way or type /help."
    )


# ============================================================
# ERROR HANDLER
# ============================================================

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error("Telegram update processing error: %s", context.error, exc_info=context.error)


# ============================================================
# START / STOP TELEGRAM BOT
# ============================================================

async def start_telegram_bot() -> Application:
    token = settings.TELEGRAM_BOT_TOKEN.strip()
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN is missing from backend/.env")
    if not settings.TELEGRAM_BOT_ENABLED:
        raise RuntimeError("Telegram bot is disabled in backend/.env")

    logger.info("Building FloodPulse AI Telegram application...")
    application = Application.builder().token(token).build()

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("weather", weather_command))
    application.add_handler(CommandHandler("flood", flood_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_message_handler))
    application.add_error_handler(error_handler)

    initialized = False
    try:
        await application.initialize()
        initialized = True
        if application.updater is None:
            raise RuntimeError("Telegram polling updater is unavailable.")

        await application.start()
        await application.updater.start_polling(drop_pending_updates=False)
        logger.info("FloodPulse AI Telegram bot started successfully.")
        return application
    except Exception:
        logger.exception("Failed to start FloodPulse AI Telegram bot.")
        try:
            if application.updater is not None and application.updater.running:
                await application.updater.stop()
            if application.running:
                await application.stop()
            if initialized:
                await application.shutdown()
        except Exception:
            logger.exception("Error during Telegram startup cleanup.")
        raise


async def stop_telegram_bot(application: Application):
    logger.info("Stopping FloodPulse AI Telegram bot...")
    try:
        if application.updater is not None and application.updater.running:
            await application.updater.stop()
        if application.running:
            await application.stop()
    finally:
        await application.shutdown()
    logger.info("FloodPulse AI Telegram bot stopped successfully.")