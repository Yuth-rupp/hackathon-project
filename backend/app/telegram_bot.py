
"""
FloodPulse AI - Telegram Bot Integration

Interactive Telegram assistant for Cambodia flood monitoring
and Tonle Sap Lake community awareness.
"""

import logging

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from app.config import settings


logger = logging.getLogger("floodpulse.telegram")


# =========================================================
# COMMAND HANDLERS
# =========================================================

async def start_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    """Handle the /start command."""

    if not update.message:
        return

    await update.message.reply_text(
        "🌊 Welcome to FloodPulse AI!\n\n"
        "Your Cambodia flood monitoring assistant.\n\n"
        "I can help you access flood and weather information "
        "for communities around Tonle Sap Lake.\n\n"
        "Type /help to see available commands."
    )


async def help_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    """Handle the /help command."""

    if not update.message:
        return

    await update.message.reply_text(
        "🌊 FLOODPULSE AI - AVAILABLE COMMANDS\n\n"
        "/start - Start the assistant\n"
        "/help - Show available commands\n"
        "/weather - Weather information\n"
        "/flood - Flood monitoring information\n\n"
        "You can also send messages such as:\n"
        "• hello\n"
        "• hi\n"
        "• hey\n"
        "• thanks\n"
        "• good morning\n"
        "• good evening\n\n"
        "FloodPulse AI - Monitoring Cambodia, "
        "Protecting Communities."
    )


async def weather_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    """Handle the /weather command."""

    if not update.message:
        return

    await update.message.reply_text(
        "🌤️ WEATHER INFORMATION\n\n"
        "Welcome to FloodPulse AI Weather Monitoring.\n\n"
        "Weather information is not yet connected "
        "to the Telegram assistant.\n\n"
        "The next development step is to connect this "
        "command to the FloodPulse weather API."
    )


async def flood_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    """Handle the /flood command."""

    if not update.message:
        return

    await update.message.reply_text(
        "🌊 FLOOD MONITORING INFORMATION\n\n"
        "Welcome to FloodPulse AI Flood Monitoring.\n\n"
        "Flood-risk information is not yet connected "
        "to this Telegram command.\n\n"
        "The next development step is to retrieve "
        "risk assessments from the FloodPulse database."
    )


# =========================================================
# GENERAL MESSAGE HANDLER
# =========================================================

async def text_message_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    """Respond to ordinary text messages."""

    if not update.message or not update.message.text:
        return

    message = update.message.text.strip().lower()

    if message in {"hello", "hi", "hey"}:

        response = (
            "🌊 Hello! Welcome to FloodPulse AI.\n\n"
            "How can I help you today?\n\n"
            "Type /help to see available commands."
        )

    elif message in {"thanks", "thank you", "thank"}:

        response = (
            "You're welcome! 😊\n\n"
            "FloodPulse AI is here to help communities "
            "stay informed and prepared."
        )

    elif message in {"good morning", "morning"}:

        response = (
            "☀️ Good morning!\n\n"
            "Welcome to FloodPulse AI.\n"
            "Stay informed and stay safe!"
        )

    elif message in {"good night", "good evening"}:

        response = (
            "🌙 Good evening!\n\n"
            "Thank you for using FloodPulse AI.\n"
            "Stay safe!"
        )

    else:

        response = (
            "🌊 Thank you for contacting FloodPulse AI!\n\n"
            "I am your flood monitoring assistant for Cambodia.\n\n"
            "I am still learning to handle more requests.\n\n"
            "Please type /help to see the available commands."
        )

    await update.message.reply_text(response)


# =========================================================
# ERROR HANDLER
# =========================================================

async def error_handler(
    update: object,
    context: ContextTypes.DEFAULT_TYPE,
):
    """Log errors raised while processing Telegram updates."""

    logger.error(
        "Telegram update processing error: %s",
        context.error,
    )


# =========================================================
# START TELEGRAM BOT
# =========================================================

async def start_telegram_bot() -> Application:
    """
    Initialize the Telegram application,
    register handlers and start polling.

    Returns:
        Application: Running Telegram application.
    """

    token = settings.TELEGRAM_BOT_TOKEN.strip()

    if not token:
        raise ValueError(
            "TELEGRAM_BOT_TOKEN is missing from backend/.env"
        )

    logger.info("Building FloodPulse AI Telegram application...")

    application = (
        Application.builder()
        .token(token)
        .build()
    )

    # Register commands
    application.add_handler(
        CommandHandler("start", start_command)
    )

    application.add_handler(
        CommandHandler("help", help_command)
    )

    application.add_handler(
        CommandHandler("weather", weather_command)
    )

    application.add_handler(
        CommandHandler("flood", flood_command)
    )

    # Register ordinary text messages
    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            text_message_handler,
        )
    )

    # Register error handler
    application.add_error_handler(error_handler)

    initialized = False

    try:
        # Initialize Telegram application
        await application.initialize()
        initialized = True

        if application.updater is None:
            raise RuntimeError(
                "Telegram polling updater is unavailable."
            )

        # Start receiving Telegram updates
        await application.updater.start_polling(
            drop_pending_updates=False
        )

        # Start processing updates
        await application.start()

        logger.info(
            "FloodPulse AI Telegram bot started successfully."
        )

        return application

    except Exception:

        logger.exception(
            "Failed to start FloodPulse AI Telegram bot."
        )

        # Clean up partially started services
        try:
            if (
                application.updater is not None
                and application.updater.running
            ):
                await application.updater.stop()

            if application.running:
                await application.stop()

            if initialized:
                await application.shutdown()

        except Exception:
            logger.exception(
                "Error during Telegram startup cleanup."
            )

        raise


# =========================================================
# STOP TELEGRAM BOT
# =========================================================

async def stop_telegram_bot(
    application: Application,
):
    """
    Stop Telegram polling and gracefully shut down
    the Telegram application.
    """

    logger.info("Stopping FloodPulse AI Telegram bot...")

    try:

        # Stop receiving updates
        if (
            application.updater is not None
            and application.updater.running
        ):
            await application.updater.stop()

        # Stop application processing
        if application.running:
            await application.stop()

    finally:

        # Release Telegram application resources
        await application.shutdown()

    logger.info(
        "FloodPulse AI Telegram bot stopped successfully."
    )
