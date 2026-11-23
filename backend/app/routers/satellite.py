"""
FloodPulse AI - Earth Observation & Satellite Data Router

Features:
- Sentinel-1 SAR STAC discovery
- Real satellite acquisition metadata
- Satellite scene processing
- Satellite freshness monitoring
- Historical acquisition database
- JRC Global Surface Water layers
- GeoTIFF upload and validation

IMPORTANT:
Sentinel-1 scene footprints are not flood boundaries.
Water extent is a preliminary SAR classification result.
"""

import asyncio
import json
import logging
import re
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from statistics import median
from typing import Dict, Any, List, Optional

import aiosqlite
import httpx

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Response,
    UploadFile,
    File,
)

from pydantic import BaseModel

from app.database import get_db
from app.config import settings

from app.services.sar_processing import (
    ProcessingError,
    process_scene as run_sar_processing,
)

from app.services.satellite_catalog import (
    iso_utc,
    parse_dt,
    parse_stac_feature,
    row_to_scene,
    store_scene,
)

from app.connectors.jrc import JRCConnector


logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/satellite",
    tags=["Satellite & EO"],
)


# ============================================================
# CONFIGURATION
# ============================================================

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

UPLOAD_DIR = DATA_DIR / "uploads"

UPLOAD_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

FRESH_HOURS = 72
AGING_HOURS = 168

SEARCH_CACHE_TTL_SECONDS = 60

_search_cache: Dict[str, Any] = {}

SOURCE_NAME_LIKE = "%Sentinel-1 STAC%"


STAC_PROVIDERS = [
    (
        "Copernicus Data Space",
        None,
        None,
    ),
    (
        "Element84 Earth Search",
        "https://earth-search.aws.element84.com/v1/search",
        "sentinel-1-grd",
    ),
    (
        "Microsoft Planetary Computer",
        "https://planetarycomputer.microsoft.com/api/stac/v1/search",
        "sentinel-1-grd",
    ),
]

STAC_TIMEOUT = httpx.Timeout(
    connect=10.0,
    read=45.0,
    write=10.0,
    pool=10.0,
)


# ============================================================
# RESPONSE MODELS
# ============================================================

class SatelliteScene(BaseModel):

    id: Optional[int] = None

    scene_id: Optional[str] = None

    satellite: str

    platform: Optional[str] = None

    acquisition_date: str

    published_at: Optional[str] = None

    collection: Optional[str] = None

    orbit_state: Optional[str] = None

    relative_orbit: Optional[int] = None

    instrument_mode: Optional[str] = None

    polarization: Optional[str] = None

    cloud_cover: Optional[float] = None

    water_extent_km2: Optional[float] = None

    stac_url: Optional[str] = None

    thumbnail_url: Optional[str] = None

    bbox: Optional[List[float]] = None

    processed: bool = False

    source: str = "live"

    checked_at: Optional[str] = None


class CatalogStatus(BaseModel):

    last_successful_fetch: Optional[str] = None

    last_error: Optional[str] = None

    last_error_time: Optional[str] = None

    source_status: Optional[str] = None

    check_interval_minutes: int


class LatestScene(BaseModel):

    scene_id: Optional[str] = None

    satellite: str

    acquisition_date: str

    published_at: Optional[str] = None

    orbit_state: Optional[str] = None

    relative_orbit: Optional[int] = None

    age_hours: float


class SatelliteStatusResponse(BaseModel):

    server_time: str

    freshness: str

    latest_scene: Optional[LatestScene] = None

    catalog: CatalogStatus

    scenes_last_7d: int

    scenes_last_30d: int

    typical_revisit_hours: Optional[float] = None

    estimated_next_pass: Optional[str] = None


class JRCLayerConfig(BaseModel):

    key: str

    name: str

    description: str

    range: str

    tile_url: str

    geotiff_url: str


class JRCLayersResponse(BaseModel):

    dataset: Dict[str, Any]

    layers: List[JRCLayerConfig]


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def _validate_date(
    value: Optional[str],
    name: str,
) -> None:

    if value is None:
        return

    try:

        datetime.strptime(
            value,
            "%Y-%m-%d",
        )

    except ValueError:

        raise HTTPException(
            status_code=422,
            detail=f"{name} must be YYYY-MM-DD",
        )


def _err_text(exc: Exception) -> str:

    detail = str(exc).strip()

    return (
        f"{type(exc).__name__}: {detail}"
        if detail
        else type(exc).__name__
    )


async def _record_catalog_result(
    db: aiosqlite.Connection,
    ok: bool,
    error: Optional[str] = None,
) -> None:

    now_iso = datetime.now(
        timezone.utc
    ).isoformat()

    try:

        if ok:

            await db.execute(
                """
                UPDATE data_sources
                SET status = 'active',
                    last_successful_fetch = ?,
                    last_error = NULL
                WHERE name LIKE ?
                """,
                (
                    now_iso,
                    SOURCE_NAME_LIKE,
                ),
            )

        else:

            await db.execute(
                """
                UPDATE data_sources
                SET last_error = ?,
                    last_error_time = ?
                WHERE name LIKE ?
                """,
                (
                    (error or "unknown error")[:300],
                    now_iso,
                    SOURCE_NAME_LIKE,
                ),
            )

        await db.commit()

    except Exception as exc:

        logger.warning(
            "Could not record satellite catalog result: %s",
            exc,
        )


async def _post_search(
    client: httpx.AsyncClient,
    url: str,
    payload: Dict[str, Any],
) -> List[Dict[str, Any]]:

    resp = await client.post(
        url,
        json=payload,
    )

    if resp.status_code in (400, 422) and "sortby" in payload:

        payload = {
            key: value
            for key, value in payload.items()
            if key != "sortby"
        }

        resp = await client.post(
            url,
            json=payload,
        )

    resp.raise_for_status()

    return resp.json().get(
        "features",
        [],
    )


async def _query_stac(
    payload: Dict[str, Any],
):

    errors = []

    async with httpx.AsyncClient(
        timeout=STAC_TIMEOUT,
        follow_redirects=True,
    ) as client:

        for name, url, collection in STAC_PROVIDERS:

            url = (
                url
                or settings.COPERNICUS_STAC_URL
            )

            collection = (
                collection
                or settings.COPERNICUS_COLLECTION
            )

            body = {
                **payload,
                "collections": [collection],
            }

            for attempt in (1, 2):

                try:

                    features = await _post_search(
                        client,
                        url,
                        body,
                    )

                    return (
                        features,
                        name,
                        collection,
                    )

                except Exception as exc:

                    error = _err_text(exc)

                    logger.warning(
                        "STAC %s attempt %s failed: %s",
                        name,
                        attempt,
                        error,
                    )

                    if (
                        attempt == 2
                        or isinstance(
                            exc,
                            httpx.HTTPStatusError,
                        )
                    ):

                        errors.append(
                            f"{name}: {error}"
                        )

                        break

    raise RuntimeError(
        " | ".join(errors)
    )


def _set_catalog_headers(
    response: Optional[Response],
    source: str,
    provider: Optional[str],
    error: Optional[str],
) -> None:

    if response is None:
        return

    response.headers["X-Catalog-Source"] = source

    if provider:

        response.headers["X-Catalog-Provider"] = provider

    if error:

        response.headers["X-Catalog-Error"] = (
            error.encode(
                "ascii",
                "ignore",
            ).decode()[:300]
        )


# ============================================================
# SATELLITE HEALTH
# ============================================================

@router.get("/health")
async def stac_health() -> Dict[str, Any]:

    now = datetime.now(timezone.utc)

    payload = {
        "bbox": settings.TONLE_SAP_BBOX,
        "datetime": (
            f"{(now - timedelta(days=30)).strftime('%Y-%m-%d')}"
            f"T00:00:00Z/"
            f"{now.strftime('%Y-%m-%d')}T23:59:59Z"
        ),
        "limit": 1,
    }

    report = []

    async with httpx.AsyncClient(
        timeout=STAC_TIMEOUT,
        follow_redirects=True,
    ) as client:

        for name, url, collection in STAC_PROVIDERS:

            url = (
                url
                or settings.COPERNICUS_STAC_URL
            )

            collection = (
                collection
                or settings.COPERNICUS_COLLECTION
            )

            started = time.monotonic()

            try:

                features = await _post_search(
                    client,
                    url,
                    {
                        **payload,
                        "collections": [collection],
                    },
                )

                report.append({
                    "provider": name,
                    "ok": True,
                    "scenes_returned": len(features),
                    "seconds": round(
                        time.monotonic() - started,
                        2,
                    ),
                })

            except Exception as exc:

                report.append({
                    "provider": name,
                    "ok": False,
                    "error": _err_text(exc),
                    "seconds": round(
                        time.monotonic() - started,
                        2,
                    ),
                })

    return {
        "checked_at": iso_utc(now),
        "providers": report,
    }


# ============================================================
# SEARCH SENTINEL-1 SCENES
# ============================================================

@router.get(
    "/search",
    response_model=List[SatelliteScene],
)
async def search_stac_catalog(
    start_date: Optional[str] = Query(
        None,
        description="Start date YYYY-MM-DD",
    ),

    end_date: Optional[str] = Query(
        None,
        description="End date YYYY-MM-DD",
    ),

    bbox: Optional[str] = Query(
        None,
        description="min_lon,min_lat,max_lon,max_lat",
    ),

    limit: int = Query(
        10,
        ge=1,
        le=50,
    ),

    response: Response = None,

    db: aiosqlite.Connection = Depends(get_db),

) -> List[SatelliteScene]:

    _validate_date(
        start_date,
        "start_date",
    )

    _validate_date(
        end_date,
        "end_date",
    )

    now = datetime.now(timezone.utc)

    s_date = (
        start_date
        or (now - timedelta(days=14)).strftime("%Y-%m-%d")
    )

    e_date = (
        end_date
        or now.strftime("%Y-%m-%d")
    )

    if s_date > e_date:

        raise HTTPException(
            status_code=422,
            detail="start_date cannot be after end_date",
        )

    target_bbox = settings.TONLE_SAP_BBOX

    if bbox:

        try:

            parsed = [
                float(x.strip())
                for x in bbox.split(",")
            ]

            if len(parsed) != 4:
                raise ValueError()

            min_lon, min_lat, max_lon, max_lat = parsed

            if not (
                -180 <= min_lon < max_lon <= 180
                and -90 <= min_lat < max_lat <= 90
            ):
                raise ValueError()

            target_bbox = parsed

        except ValueError:

            raise HTTPException(
                status_code=422,
                detail="Invalid bounding box coordinates",
            )

    cache_key = json.dumps([
        s_date,
        e_date,
        target_bbox,
        limit,
    ])

    hit = _search_cache.get(cache_key)

    if (
        hit
        and time.monotonic() - hit[0]
        < SEARCH_CACHE_TTL_SECONDS
    ):

        _set_catalog_headers(
            response,
            "live",
            hit[2],
            None,
        )

        return hit[1]

    payload = {
        "bbox": target_bbox,

        "datetime": (
            f"{s_date}T00:00:00Z/"
            f"{e_date}T23:59:59Z"
        ),

        "limit": limit,

        "sortby": [
            {
                "field": "properties.datetime",
                "direction": "desc",
            }
        ],
    }

    checked_at = iso_utc(now)

    scenes = []

    source = "live"

    provider = None

    catalog_error = None

    try:

        features, provider, used_collection = await _query_stac(
            payload
        )

        for feature in features:

            parsed_scene = parse_stac_feature(
                feature,
                used_collection,
            )

            if parsed_scene:
                scenes.append(parsed_scene)

        scenes.sort(
            key=lambda scene: scene["acquisition_date"],
            reverse=True,
        )

        scenes = scenes[:limit]

        for scene in scenes:

            await store_scene(
                db,
                scene,
            )

        await db.commit()

        for scene in scenes:

            cursor = await db.execute(
                """
                SELECT water_extent_km2, processed
                FROM satellite_acquisitions
                WHERE stac_url = ?
                LIMIT 1
                """,
                (scene.get("stac_url"),),
            )

            stored = await cursor.fetchone()

            if stored:

                scene["water_extent_km2"] = stored["water_extent_km2"]

                scene["processed"] = bool(
                    stored["processed"]
                )

        await _record_catalog_result(
            db,
            ok=True,
        )

    except Exception as exc:

        logger.warning(
            "Live STAC search failed: %s",
            exc,
        )

        catalog_error = _err_text(exc)

        await _record_catalog_result(
            db,
            ok=False,
            error=catalog_error,
        )

        source = "cache"

        cursor = await db.execute(
            """
            SELECT
                id,
                satellite,
                acquisition_date,
                collection,
                orbit_state,
                instrument_mode,
                bbox_geojson,
                cloud_cover,
                water_extent_km2,
                stac_url,
                thumbnail_url,
                processed,
                metadata_json

            FROM satellite_acquisitions

            WHERE COALESCE(collection, '') != 'admin_upload'
              AND substr(acquisition_date, 1, 10)
                  BETWEEN ? AND ?

            ORDER BY acquisition_date DESC

            LIMIT ?
            """,
            (
                s_date,
                e_date,
                limit,
            ),
        )

        scenes = [
            row_to_scene(row)
            for row in await cursor.fetchall()
        ]

    results = [
        SatelliteScene(
            **{
                key: value
                for key, value in scene.items()
                if key in SatelliteScene.model_fields
            },

            source=source,

            checked_at=checked_at,
        )

        for scene in scenes
    ]

    _set_catalog_headers(
        response,
        source,
        provider,
        catalog_error,
    )

    if source == "live":

        _search_cache[cache_key] = (
            time.monotonic(),
            results,
            provider,
        )

    return results


# ============================================================
# PROCESS SENTINEL-1 SCENE
# ============================================================

@router.post("/process")
async def process_scene_water_extent(
    scene_id: str = Query(
        ...,
        description="Database ID or STAC scene ID returned by /satellite/search",
    ),
    db: aiosqlite.Connection = Depends(get_db),
) -> Dict[str, Any]:
    """Process a Sentinel-1 scene and save its result to the matching row.

    The frontend may send the database row ID (acq.id), while other callers
    may send the STAC scene ID. Resolve both forms without changing records.
    """

    row = None

    # The frontend currently sends acq.id, which is the database primary key.
    try:
        database_id = int(scene_id)
    except (TypeError, ValueError):
        database_id = None

    if database_id is not None:
        cursor = await db.execute(
            """
            SELECT id, acquisition_date, metadata_json, stac_url
            FROM satellite_acquisitions
            WHERE id = ?
            LIMIT 1
            """,
            (database_id,),
        )
        row = await cursor.fetchone()

    # Backward-compatible lookup for callers sending the STAC item ID.
    if row is None:
        cursor = await db.execute(
            """
            SELECT id, acquisition_date, metadata_json, stac_url
            FROM satellite_acquisitions
            ORDER BY id DESC
            """
        )
        candidates = await cursor.fetchall()

        for candidate in candidates:
            try:
                candidate_metadata = json.loads(
                    candidate["metadata_json"] or "{}"
                )
            except (ValueError, TypeError):
                candidate_metadata = {}

            stored_scene_id = str(
                candidate_metadata.get("scene_id")
                or candidate_metadata.get("stac_id")
                or ""
            )
            stored_url = str(candidate["stac_url"] or "")
            stored_url_id = stored_url.rstrip("/").split("/")[-1]

            if stored_scene_id == scene_id or stored_url_id == scene_id:
                row = candidate
                break

    if row is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"Satellite scene '{scene_id}' was not found. "
                "Run satellite search again."
            ),
        )

    try:
        metadata = json.loads(row["metadata_json"] or "{}")
    except (ValueError, TypeError):
        metadata = {}

    actual_scene_id = (
        metadata.get("scene_id")
        or metadata.get("stac_id")
        or str(row["stac_url"] or "").rstrip("/").split("/")[-1]
        or scene_id
    )

    logger.info(
        "Starting SAR processing: database_id=%s, scene_id=%s",
        row["id"],
        actual_scene_id,
    )

    try:
        result = await asyncio.to_thread(
            run_sar_processing,
            row["acquisition_date"],
            metadata.get("platform"),
            settings.TONLE_SAP_BBOX,
        )
    except ProcessingError as exc:
        logger.warning(
            "SAR processing unavailable for scene %s: %s",
            actual_scene_id,
            exc,
        )
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        )
    except Exception as exc:
        logger.exception(
            "SAR processing failed for scene %s",
            actual_scene_id,
        )
        raise HTTPException(
            status_code=502,
            detail=f"Processing failed: {_err_text(exc)}",
        )

    metadata["processing"] = result

    await db.execute(
        """
        UPDATE satellite_acquisitions
        SET processed = 1,
            water_extent_km2 = ?,
            metadata_json = ?
        WHERE id = ?
        """,
        (
            result["water_extent_km2"],
            json.dumps(metadata),
            row["id"],
        ),
    )
    await db.commit()

    # Force the next catalog request to reload the saved processed status.
    _search_cache.clear()

    logger.info(
        "SAR processing completed: database_id=%s, scene_id=%s, water_extent=%s km2",
        row["id"],
        actual_scene_id,
        result["water_extent_km2"],
    )

    return {
        "success": True,
        "database_id": row["id"],
        "scene_id": actual_scene_id,
        **result,
    }


# ============================================================
# SATELLITE STATUS
# ============================================================

@router.get(
    "/status",
    response_model=SatelliteStatusResponse,
)
async def get_satellite_status(
    db: aiosqlite.Connection = Depends(get_db),
) -> SatelliteStatusResponse:

    now = datetime.now(timezone.utc)

    cursor = await db.execute(
        """
        SELECT
            acquisition_date,
            satellite,
            orbit_state,
            metadata_json,
            stac_url

        FROM satellite_acquisitions

        WHERE COALESCE(collection, '') != 'admin_upload'

        ORDER BY acquisition_date DESC

        LIMIT 400
        """
    )

    rows = await cursor.fetchall()

    stamped = []

    for row in rows:

        dt = parse_dt(
            row["acquisition_date"]
        )

        if dt:
            stamped.append((dt, row))

    stamped.sort(
        key=lambda item: item[0],
        reverse=True,
    )

    latest = None

    freshness = "unknown"

    if stamped:

        dt, row = stamped[0]

        scene = row_to_scene({
            "id": None,

            "satellite": row["satellite"],

            "acquisition_date": row["acquisition_date"],

            "collection": None,

            "orbit_state": row["orbit_state"],

            "instrument_mode": None,

            "bbox_geojson": None,

            "cloud_cover": None,

            "water_extent_km2": None,

            "stac_url": row["stac_url"],

            "thumbnail_url": None,

            "processed": 0,

            "metadata_json": row["metadata_json"],
        })

        age_hours = max(
            (now - dt).total_seconds() / 3600,
            0,
        )

        latest = LatestScene(
            scene_id=scene["scene_id"],

            satellite=row["satellite"],

            acquisition_date=(
                iso_utc(dt)
                or row["acquisition_date"]
            ),

            published_at=scene["published_at"],

            orbit_state=scene["orbit_state"],

            relative_orbit=scene["relative_orbit"],

            age_hours=round(age_hours, 2),
        )

        if age_hours <= FRESH_HOURS:
            freshness = "fresh"

        elif age_hours <= AGING_HOURS:
            freshness = "aging"

        else:
            freshness = "stale"

    scenes_7d = sum(
        1
        for dt, _ in stamped
        if now - dt <= timedelta(days=7)
    )

    scenes_30d = sum(
        1
        for dt, _ in stamped
        if now - dt <= timedelta(days=30)
    )

    typical_hours = None

    estimated_next = None

    recent = sorted(
        dt
        for dt, _ in stamped
        if now - dt <= timedelta(days=30)
    )

    pass_starts = []

    for dt in recent:

        if (
            not pass_starts
            or dt - pass_starts[-1] > timedelta(minutes=30)
        ):

            pass_starts.append(dt)

    if len(pass_starts) >= 4:

        gaps = [
            (b - a).total_seconds() / 3600
            for a, b in zip(
                pass_starts,
                pass_starts[1:],
            )
        ]

        typical_hours = round(
            median(gaps),
            1,
        )

        if typical_hours > 0:

            next_pass = (
                pass_starts[-1]
                + timedelta(hours=typical_hours)
            )

            while next_pass <= now:

                next_pass += timedelta(
                    hours=typical_hours
                )

            estimated_next = iso_utc(
                next_pass
            )

    src_cursor = await db.execute(
        """
        SELECT
            status,
            last_successful_fetch,
            last_error,
            last_error_time

        FROM data_sources

        WHERE name LIKE ?

        LIMIT 1
        """,
        (SOURCE_NAME_LIKE,),
    )

    src = await src_cursor.fetchone()

    interval = int(
        getattr(
            settings,
            "SATELLITE_CATALOG_CHECK_MINUTES",
            60,
        )
    )

    return SatelliteStatusResponse(
        server_time=iso_utc(now) or "",

        freshness=freshness,

        latest_scene=latest,

        catalog=CatalogStatus(
            last_successful_fetch=(
                iso_utc(parse_dt(src["last_successful_fetch"]))
                if src else None
            ),

            last_error=(
                src["last_error"]
                if src else None
            ),

            last_error_time=(
                iso_utc(parse_dt(src["last_error_time"]))
                if src else None
            ),

            source_status=(
                src["status"]
                if src else None
            ),

            check_interval_minutes=interval,
        ),

        scenes_last_7d=scenes_7d,

        scenes_last_30d=scenes_30d,

        typical_revisit_hours=typical_hours,

        estimated_next_pass=estimated_next,
    )


# ============================================================
# STORED ACQUISITIONS
# ============================================================

@router.get(
    "/acquisitions",
    response_model=List[SatelliteScene],
)
async def list_stored_acquisitions(
    satellite: Optional[str] = Query(None),

    limit: int = Query(
        50,
        ge=1,
        le=200,
    ),

    db: aiosqlite.Connection = Depends(get_db),

) -> List[SatelliteScene]:

    query = """
        SELECT
            id,
            satellite,
            acquisition_date,
            collection,
            orbit_state,
            instrument_mode,
            bbox_geojson,
            cloud_cover,
            water_extent_km2,
            stac_url,
            thumbnail_url,
            processed,
            metadata_json

        FROM satellite_acquisitions
    """

    params = []

    if satellite:

        query += " WHERE satellite LIKE ?"

        params.append(
            f"%{satellite}%"
        )

    query += """
        ORDER BY acquisition_date DESC
        LIMIT ?
    """

    params.append(limit)

    cursor = await db.execute(
        query,
        tuple(params),
    )

    rows = await cursor.fetchall()

    return [
        SatelliteScene(
            **{
                key: value
                for key, value in row_to_scene(row).items()
                if key in SatelliteScene.model_fields
            },

            source="cache",
        )

        for row in rows
    ]


# ============================================================
# JRC GLOBAL SURFACE WATER LAYERS
# ============================================================

@router.get(
    "/jrc/layers",
    response_model=JRCLayersResponse,
)
async def get_jrc_layers() -> JRCLayersResponse:

    """
    Return historical JRC Global Surface Water layer metadata.

    JRC Global Surface Water v1.4:
    - 1984-2021
    - Landsat 5, 7 and 8
    - 30 metre resolution

    These are historical water observations,
    not real-time flood detections.
    """

    try:

        connector = JRCConnector()

        metadata = connector.get_dataset_metadata()

        layers = []

        for key, config in connector.LAYERS.items():

            layers.append(
                JRCLayerConfig(
                    key=key,

                    name=config["name"],

                    description=config["description"],

                    range=config["range"],

                    tile_url=connector.get_tile_template_url(key),

                    geotiff_url=connector.get_geotiff_download_url(key),
                )
            )

        return JRCLayersResponse(
            dataset=metadata,
            layers=layers,
        )

    except Exception as exc:

        logger.exception(
            "JRC layer configuration failed"
        )

        raise HTTPException(
            status_code=500,
            detail=f"Could not load JRC configuration: {_err_text(exc)}",
        )


# ============================================================
# GEOTIFF UPLOAD
# ============================================================

@router.post("/upload")
async def upload_satellite_raster(
    file: UploadFile = File(...),
) -> Dict[str, Any]:

    """
    Accept a GeoTIFF file for subsequent satellite raster processing.

    This endpoint validates and stores the uploaded file.
    It does NOT automatically classify the image as flooded.
    """

    allowed_extensions = {
        ".tif",
        ".tiff",
    }

    filename = Path(
        file.filename or ""
    ).name

    extension = Path(
        filename
    ).suffix.lower()

    if extension not in allowed_extensions:

        raise HTTPException(
            status_code=400,
            detail="Only .tif and .tiff files are accepted.",
        )

    safe_name = re.sub(
        r"[^a-zA-Z0-9_.-]",
        "_",
        filename,
    )

    timestamp = datetime.now(
        timezone.utc
    ).strftime("%Y%m%d_%H%M%S_%f")

    destination = UPLOAD_DIR / f"{timestamp}_{safe_name}"

    max_size = 500 * 1024 * 1024

    total_size = 0

    try:

        with destination.open("wb") as output:

            while True:

                chunk = await file.read(1024 * 1024)

                if not chunk:
                    break

                total_size += len(chunk)

                if total_size > max_size:

                    raise HTTPException(
                        status_code=413,
                        detail="File exceeds the 500 MB upload limit.",
                    )

                output.write(chunk)

        if total_size == 0:

            raise HTTPException(
                status_code=400,
                detail="Uploaded file is empty.",
            )

        # Validate the raster if rasterio is installed.
        try:

            import rasterio

            with rasterio.open(destination) as dataset:

                raster_info = {
                    "width": dataset.width,

                    "height": dataset.height,

                    "bands": dataset.count,

                    "crs": (
                        str(dataset.crs)
                        if dataset.crs
                        else None
                    ),

                    "bounds": list(dataset.bounds),

                    "resolution": list(dataset.res),

                    "driver": dataset.driver,
                }

        except ImportError:

            raster_info = {
                "validation": "File stored; rasterio is not installed."
            }

        except Exception as exc:

            destination.unlink(missing_ok=True)

            raise HTTPException(
                status_code=422,
                detail=f"Invalid or unreadable GeoTIFF: {str(exc)}",
            )

        return {
            "success": True,

            "message": "Satellite raster uploaded successfully.",

            "filename": filename,

            "stored_filename": destination.name,

            "size_bytes": total_size,

            "size_mb": round(
                total_size / (1024 * 1024),
                2,
            ),

            "processing_status": "uploaded_not_processed",

            "raster": raster_info,
        }

    except HTTPException:

        destination.unlink(missing_ok=True)

        raise

    except Exception as exc:

        destination.unlink(missing_ok=True)

        logger.exception(
            "Satellite upload failed"
        )

        raise HTTPException(
            status_code=500,
            detail=f"Upload failed: {_err_text(exc)}",
        )

    finally:

        await file.close()