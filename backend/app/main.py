
"""
FloodPulse AI - FastAPI Core Application
Tonle Sap Lake Flood Monitoring Platform for Cambodia.

Backend orchestration:
- FastAPI application lifecycle
- CORS configuration
- SQLite database initialization
- Background weather synchronization
- Copernicus satellite catalog monitoring
- Telegram interactive bot integration
- API routing
"""

import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import settings
from app.database import init_db, get_db_path, fetch_one
from app.models import HealthCheckResponse

from app.connectors.open_meteo import OpenMeteoConnector
from app.connectors.copernicus import CopernicusSTACConnector

from app.telegram_bot import (
    start_telegram_bot,
    stop_telegram_bot,
)


# =========================================================
# API ROUTERS
# =========================================================

from app.routers import (
    stations,
    weather,
    satellite,
    alerts,
    risk,
    dashboard,
    sources,
    hydrology,
    community,
    data_sources,
    admin,
)


# =========================================================
# APPLICATION LOGGING
# =========================================================

logging.basicConfig(
    level=getattr(
        logging,
        settings.LOG_LEVEL.upper(),
        logging.INFO,
    ),
    format=(
        "%(asctime)s [%(levelname)s] "
        "[%(name)s]: %(message)s"
    ),
)

logger = logging.getLogger("floodpulse.main")


# =========================================================
# BACKGROUND SCHEDULER
# =========================================================

scheduler = AsyncIOScheduler()


async def scheduled_weather_sync():
    """
    Periodically synchronize weather and GloFAS discharge
    forecasts for monitoring locations.
    """

    logger.info(
        "Scheduler: Starting weather synchronization..."
    )

    try:
        connector = OpenMeteoConnector()

        result = await connector.sync_all_monitoring_locations()

        logger.info(
            "Scheduler: Weather synchronization completed "
            "(%s locations).",
            result.get("synced_locations"),
        )

    except Exception:
        logger.exception(
            "Scheduler: Error during weather synchronization."
        )


async def scheduled_satellite_check():
    """
    Periodically check Copernicus STAC for new Sentinel-1 scenes.
    """

    logger.info(
        "Scheduler: Checking Copernicus STAC catalog..."
    )

    try:
        stac = CopernicusSTACConnector()

        scenes = await stac.search_acquisitions(limit=10)

        logger.info(
            "Scheduler: Satellite catalog check completed "
            "(%s scenes processed).",
            len(scenes),
        )

    except Exception:
        logger.exception(
            "Scheduler: Error during satellite catalog check."
        )


# =========================================================
# APPLICATION LIFECYCLE
# =========================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Initialize the database, scheduler and Telegram bot
    when FastAPI starts.

    Gracefully stop background services when FastAPI shuts down.
    """

    logger.info(
        "Starting FloodPulse AI application..."
    )

    telegram_application = None

    try:

        # 1. Initialize database
        await init_db()

        logger.info(
            "Database initialized successfully."
        )

        # 2. Configure background scheduler
        if settings.SCHEDULER_ENABLED:

            logger.info(
                "Initializing background scheduler jobs..."
            )

            scheduler.add_job(
                scheduled_weather_sync,
                "interval",
                minutes=settings.WEATHER_REFRESH_INTERVAL_MINUTES,
                id="job_weather_sync",
                replace_existing=True,
            )

            scheduler.add_job(
                scheduled_satellite_check,
                "interval",
                hours=settings.SATELLITE_CATALOG_CHECK_HOURS,
                id="job_satellite_check",
                replace_existing=True,
            )

            if not scheduler.running:
                scheduler.start()

            logger.info(
                "Scheduler active: Weather sync every %s minutes; "
                "satellite check every %s hours.",
                settings.WEATHER_REFRESH_INTERVAL_MINUTES,
                settings.SATELLITE_CATALOG_CHECK_HOURS,
            )

        # 3. Start Telegram bot
        if settings.TELEGRAM_BOT_ENABLED:

            logger.info(
                "Initializing FloodPulse AI Telegram bot..."
            )

            telegram_application = await start_telegram_bot()

            logger.info(
                "Telegram bot is now listening for messages."
            )

        else:

            logger.info(
                "Telegram bot is disabled. "
                "Set TELEGRAM_BOT_ENABLED=true in .env to enable it."
            )

        # 4. Application is ready
        logger.info(
            "FloodPulse AI application startup completed."
        )

        yield

    finally:

        # 5. Stop Telegram bot
        if telegram_application is not None:

            logger.info(
                "Stopping Telegram bot..."
            )

            try:

                await stop_telegram_bot(
                    telegram_application
                )

            except Exception:

                logger.exception(
                    "Error while stopping Telegram bot."
                )

        # 6. Stop background scheduler
        if scheduler.running:

            logger.info(
                "Stopping background scheduler..."
            )

            scheduler.shutdown(wait=False)

        logger.info(
            "FloodPulse AI backend shutdown complete."
        )


# =========================================================
# FASTAPI APPLICATION
# =========================================================

app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    description=(
        "Competition-ready Tonle Sap Lake Flood Monitoring "
        "Platform for Cambodia. "
        "Provides real-time hydrological tracking, "
        "high-resolution Open-Meteo forecasts, "
        "Copernicus Sentinel-1 SAR cataloging, "
        "JRC Global Surface Water layers, "
        "ODC disaster impact information, "
        "and automated Telegram integration."
    ),
    lifespan=lifespan,
)


# =========================================================
# CORS CONFIGURATION
# =========================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =========================================================
# API ROUTERS - VERSIONED PREFIX
# =========================================================

app.include_router(stations.router, prefix="/api/v1")
app.include_router(weather.router, prefix="/api/v1")
app.include_router(satellite.router, prefix="/api/v1")
app.include_router(alerts.router, prefix="/api/v1")
app.include_router(risk.router, prefix="/api/v1")
app.include_router(dashboard.router, prefix="/api/v1")
app.include_router(sources.router, prefix="/api/v1")
app.include_router(hydrology.router, prefix="/api/v1")
app.include_router(community.router, prefix="/api/v1")
app.include_router(data_sources.router, prefix="/api/v1")
app.include_router(admin.router, prefix="/api/v1")


# =========================================================
# DIRECT ROUTER ACCESS
# =========================================================

app.include_router(hydrology.router)
app.include_router(community.router)
app.include_router(data_sources.router)
app.include_router(admin.router)
app.include_router(dashboard.router)
app.include_router(weather.router)
app.include_router(satellite.router)
app.include_router(risk.router)
app.include_router(alerts.router)


# =========================================================
# ROOT ENDPOINT
# =========================================================

@app.get("/", tags=["General"])
async def root():
    """
    Return general application information.
    """

    return {
        "app": settings.APP_NAME,
        "version": "1.0.0",
        "description": (
            "Tonle Sap Lake Flood Monitoring Platform (Cambodia)"
        ),
        "docs_url": "/docs",
        "openapi_url": "/openapi.json",

        "api_v1_endpoints": {
            "stations": "/api/v1/stations",

            "monitoring_locations": (
                "/api/v1/monitoring-locations"
            ),

            "weather_current": (
                "/api/v1/weather/current/{location_id}"
            ),

            "weather_forecast": (
                "/api/v1/weather/forecast/{location_id}"
            ),

            "river_discharge": (
                "/api/v1/weather/discharge/{location_id}"
            ),

            "satellite_acquisitions": (
                "/api/v1/satellite/acquisitions"
            ),

            "satellite_latest": (
                "/api/v1/satellite/latest"
            ),

            "jrc_metadata": "/api/v1/jrc/metadata",

            "jrc_tiles": "/api/v1/jrc/tiles/{layer}",

            "alerts": "/api/v1/alerts",

            "risk_assessments": (
                "/api/v1/risk/assessments"
            ),

            "dashboard_kpis": (
                "/api/v1/dashboard/kpis"
            ),

            "flood_events": "/api/v1/flood-events",

            "data_sources": "/api/v1/data-sources",
        },

        "telegram_bot_enabled": (
            settings.TELEGRAM_BOT_ENABLED
        ),

        "status": "operational",
    }


# =========================================================
# HEALTH CHECK ENDPOINT
# =========================================================

@app.get(
    "/health",
    response_model=HealthCheckResponse,
    tags=["General"],
)
async def health_check():
    """
    Return system health diagnostics, database status,
    active data sources and scheduler status.
    """

    now_utc = datetime.now(
        timezone.utc
    ).isoformat()

    db_connected = False
    active_sources = 0

    try:

        row = await fetch_one(
            """
            SELECT COUNT(*) AS count
            FROM data_sources
            WHERE status = 'active'
            """
        )

        if row is not None:

            db_connected = True
            active_sources = row["count"]

    except Exception:

        logger.exception(
            "Health check database query failure."
        )

    return HealthCheckResponse(
        status=(
            "healthy"
            if db_connected
            else "degraded"
        ),

        app_name=settings.APP_NAME,

        environment=settings.APP_ENV,

        database_connected=db_connected,

        database_path=get_db_path(),

        scheduler_running=scheduler.running,

        active_sources_count=active_sources,

        timestamp_utc=now_utc,
    )
