"""
FloodPulse AI - FastAPI Core Application
Tonle Sap Lake Flood Monitoring Platform for Cambodia.

Backend orchestration:
- FastAPI application lifecycle
- CORS configuration
- SQLite database initialization
- Background weather synchronization
- River discharge ingestion
- MRC gauge polling
- Copernicus satellite monitoring
- Automatic flood risk reassessment
- Emergency alert checking
- Telegram integration
- API routing
"""

import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

import aiosqlite

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import settings
from app.database import init_db, get_db_path, fetch_one, execute_query
from app.models import HealthCheckResponse

from app.connectors.open_meteo import OpenMeteoConnector
from app.connectors.copernicus import CopernicusSTACConnector

from app.services.scheduler import (
    fetch_discharge_job,
    fetch_gauge_job,
    check_alerts_job,
)

from app.services.risk_engine import risk_engine

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
    format="%(asctime)s [%(levelname)s] [%(name)s]: %(message)s",
)

logger = logging.getLogger("floodpulse.main")

# =========================================================
# BACKGROUND SCHEDULER
# =========================================================

scheduler = AsyncIOScheduler()


# =========================================================
# JOB 1: WEATHER SYNCHRONIZATION
# =========================================================

async def scheduled_weather_sync():
    """
    Synchronize Open-Meteo weather data for all
    monitoring locations.
    """

    logger.info("Starting weather synchronization...")

    try:
        connector = OpenMeteoConnector()

        result = await connector.sync_all_monitoring_locations()

        logger.info(
            "Weather synchronization completed. Locations: %s",
            result.get("synced_locations"),
        )

    except Exception:
        logger.exception("Weather synchronization failed.")
        return

    # Fresh rainfall and soil data is now stored, so recalculate risk
    # immediately instead of waiting for the next 15-minute cycle.
    await scheduled_risk_assessment()


# =========================================================
# JOB 2: SATELLITE CATALOG MONITORING
# =========================================================

async def scheduled_satellite_check():
    """
    Check Copernicus STAC for new Sentinel-1 scenes.
    """

    logger.info("Checking Copernicus STAC catalog...")

    try:
        stac = CopernicusSTACConnector()

        scenes = await stac.search_acquisitions(limit=20)

        await execute_query(
            """
            UPDATE data_sources
            SET status = 'active',
                last_successful_fetch = ?,
                last_error = NULL
            WHERE name LIKE '%Sentinel-1 STAC%'
            """,
            (datetime.now(timezone.utc).isoformat(),),
        )

        logger.info(
            "Satellite catalog check completed. Scenes: %s",
            len(scenes),
        )

    except Exception:
        logger.exception("Satellite catalog check failed.")


# =========================================================
# JOB 3: AUTOMATIC FLOOD RISK ASSESSMENT
# =========================================================

async def scheduled_risk_assessment():
    """
    Recalculate flood risk for all monitoring locations.

    This job uses the latest data already stored in SQLite.
    It does not force external providers to update their data.
    """

    logger.info("Starting automatic flood risk reassessment...")

    try:
        db_path = get_db_path()

        async with aiosqlite.connect(db_path) as db:
            db.row_factory = aiosqlite.Row

            await db.execute("PRAGMA foreign_keys = ON")

            results = await risk_engine.assess_all_locations(db)

        successful = len(results)

        logger.info(
            "Flood risk reassessment completed: %s locations.",
            successful,
        )

    except Exception:
        logger.exception("Automatic flood risk reassessment failed.")


# =========================================================
# JOB 4: AUTOMATIC EMERGENCY ALERT CHECKING
# =========================================================

async def scheduled_alert_check():
    """
    Check hydrological thresholds and generate alerts.

    Uses the existing alert_service through check_alerts_job
    in app/services/scheduler.py.
    """

    logger.info("Starting automatic emergency alert check...")

    try:
        result = await check_alerts_job()

        logger.info(
            "Emergency alert check completed. New alerts: %s",
            result.get("alerts_triggered", 0),
        )

    except Exception:
        logger.exception("Automatic emergency alert check failed.")


# =========================================================
# APPLICATION LIFECYCLE
# =========================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Initialize database, scheduler and Telegram bot
    during application startup.

    Stop background services during shutdown.
    """

    logger.info("Starting FloodPulse AI application...")

    telegram_application = None

    try:

        # -------------------------------------------------
        # 1. INITIALIZE DATABASE
        # -------------------------------------------------

        await init_db()

        logger.info("Database initialized successfully.")

        # -------------------------------------------------
        # 2. CONFIGURE BACKGROUND SCHEDULER
        # -------------------------------------------------

        if settings.SCHEDULER_ENABLED:

            logger.info("Configuring background scheduler...")

            # WEATHER SYNCHRONIZATION
            scheduler.add_job(
                scheduled_weather_sync,
                trigger="interval",
                minutes=settings.WEATHER_REFRESH_INTERVAL_MINUTES,
                id="job_weather_sync",
                name="Open-Meteo Weather Synchronization",
                replace_existing=True,
                max_instances=1,
                coalesce=True,
                # Run once at startup so rainfall and soil data exist
                # before the first risk assessment is shown.
                next_run_time=datetime.now(timezone.utc),
            )

            # RIVER DISCHARGE INGESTION
            discharge_interval = max(
                settings.DISCHARGE_REFRESH_INTERVAL_HOURS,
                6,
            )

            scheduler.add_job(
                fetch_discharge_job,
                trigger="interval",
                hours=discharge_interval,
                id="job_discharge_fetch",
                name="Open-Meteo Flood Discharge Forecast",
                replace_existing=True,
                max_instances=1,
                coalesce=True,
                next_run_time=datetime.now(timezone.utc),
            )

            # MRC GAUGE WATER LEVEL POLLING
            scheduler.add_job(
                fetch_gauge_job,
                trigger="interval",
                minutes=settings.GAUGE_REFRESH_INTERVAL_MINUTES,
                id="job_gauge_fetch",
                name="MRC Gauge Water-Level Polling",
                replace_existing=True,
                max_instances=1,
                coalesce=True,
            )

            # SATELLITE CATALOG MONITORING
            scheduler.add_job(
                scheduled_satellite_check,
                trigger="interval",
                minutes=settings.SATELLITE_CATALOG_CHECK_MINUTES,
                id="job_satellite_check",
                name="Copernicus Sentinel-1 Monitoring",
                replace_existing=True,
                max_instances=1,
                coalesce=True,
            )

            # AUTOMATIC RISK REASSESSMENT
            scheduler.add_job(
                scheduled_risk_assessment,
                trigger="interval",
                minutes=15,
                id="job_risk_assessment",
                name="Automatic Flood Risk Reassessment",
                replace_existing=True,
                max_instances=1,
                coalesce=True,
                # Give the startup weather and discharge fetches time to finish.
                next_run_time=datetime.now(timezone.utc) + timedelta(minutes=2),
            )

            # AUTOMATIC EMERGENCY ALERT CHECKING
            scheduler.add_job(
                scheduled_alert_check,
                trigger="interval",
                minutes=30,
                id="job_alert_check",
                name="Hydrological Threshold & Emergency Alert Monitor",
                replace_existing=True,
                max_instances=1,
                coalesce=True,
                next_run_time=datetime.now(timezone.utc),
            )

            # START SCHEDULER
            if not scheduler.running:
                scheduler.start()

            logger.info("Background scheduler started.")

            logger.info(
                "Weather synchronization: every %s minutes.",
                settings.WEATHER_REFRESH_INTERVAL_MINUTES,
            )

            logger.info(
                "Discharge ingestion: every %s hours.",
                discharge_interval,
            )

            logger.info(
                "Gauge polling: every %s minutes.",
                settings.GAUGE_REFRESH_INTERVAL_MINUTES,
            )

            logger.info(
                "Satellite monitoring: every %s minutes.",
                settings.SATELLITE_CATALOG_CHECK_MINUTES,
            )

            logger.info(
                "Flood risk reassessment: every 15 minutes."
            )

            logger.info(
                "Emergency alert checking: every 30 minutes."
            )

        else:
            logger.info("Background scheduler is disabled.")

        # -------------------------------------------------
        # 3. START TELEGRAM BOT
        # -------------------------------------------------

        if settings.TELEGRAM_BOT_ENABLED:

            logger.info("Starting Telegram bot...")

            # A bad or revoked token must not stop the whole API from starting.
            try:
                telegram_application = await start_telegram_bot()
                logger.info("Telegram bot started.")

            except Exception as exc:
                telegram_application = None
                logger.error(
                    "Telegram bot could not start (%s). "
                    "The API will continue without it. "
                    "Check TELEGRAM_BOT_TOKEN in backend/.env.",
                    type(exc).__name__,
                )

        else:
            logger.info("Telegram bot is disabled.")

        # -------------------------------------------------
        # 4. APPLICATION READY
        # -------------------------------------------------

        logger.info("FloodPulse AI startup completed.")

        yield

    finally:

        # -------------------------------------------------
        # 5. STOP TELEGRAM BOT
        # -------------------------------------------------

        if telegram_application is not None:

            logger.info("Stopping Telegram bot...")

            try:
                await stop_telegram_bot(telegram_application)

            except Exception:
                logger.exception("Error stopping Telegram bot.")

        # -------------------------------------------------
        # 6. STOP SCHEDULER
        # -------------------------------------------------

        if scheduler.running:

            logger.info("Stopping background scheduler...")

            scheduler.shutdown(wait=False)

        logger.info("FloodPulse AI shutdown completed.")


# =========================================================
# FASTAPI APPLICATION
# =========================================================

app = FastAPI(
    title=settings.APP_NAME,
    version="2.0.0",
    description=(
        "Tonle Sap Lake Flood Monitoring Platform for Cambodia. "
        "Provides weather monitoring, river discharge forecasts, "
        "hydrological telemetry, satellite catalog monitoring, "
        "automatic flood risk assessments and early warning APIs."
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
    expose_headers=[
        "X-Catalog-Source",
        "X-Catalog-Provider",
        "X-Catalog-Error",
    ],
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
# Preserve existing unversioned endpoints.
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
        "version": "2.0.0",
        "description": (
            "Tonle Sap Lake Flood Monitoring Platform (Cambodia)"
        ),
        "docs_url": "/docs",
        "openapi_url": "/openapi.json",
        "api_v1_endpoints": {
            "stations": "/api/v1/stations",
            "monitoring_locations": "/api/v1/monitoring-locations",
            "weather_current": "/api/v1/weather/current/{location_id}",
            "weather_forecast": "/api/v1/weather/forecast/{location_id}",
            "river_discharge": "/api/v1/weather/discharge/{location_id}",
            "satellite_acquisitions": "/api/v1/satellite/acquisitions",
            "satellite_latest": "/api/v1/satellite/latest",
            "alerts": "/api/v1/alerts",
            "risk_assessments": "/api/v1/risk/assessments",
            "risk_model_info": "/api/v1/risk/model-info",
            "risk_manual_assessment": "/api/v1/risk/assess",
            "dashboard_kpis": "/api/v1/dashboard/kpis",
            "data_sources": "/api/v1/data-sources",
        },
        "telegram_bot_enabled": settings.TELEGRAM_BOT_ENABLED,
        "scheduler_enabled": settings.SCHEDULER_ENABLED,
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
    Return system health diagnostics,
    database status, data sources and scheduler status.
    """

    now_utc = datetime.now(timezone.utc).isoformat()

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
        logger.exception("Health check database query failed.")

    return HealthCheckResponse(
        status="healthy" if db_connected else "degraded",
        app_name=settings.APP_NAME,
        environment=settings.APP_ENV,
        database_connected=db_connected,
        database_path=get_db_path(),
        scheduler_running=scheduler.running,
        active_sources_count=active_sources,
        timestamp_utc=now_utc,
    )