
"""
FloodPulse AI - Sentinel-1 SAR water-extent processing.

For one catalog scene this:
  1. finds the matching acquisition on Microsoft Planetary Computer,
  2. reads a down-sampled VV (or VH) radar band from the cloud-optimised GeoTIFF,
  3. locates pixels using the image's ground control points,
  4. keeps pixels inside the Tonle Sap bounding box,
  5. separates dark (calm open water) from bright (land) pixels using Otsu's threshold,
  6. calculates the estimated water area in km^2.

IMPORTANT:
The Planetary Computer acquisition must match the requested acquisition time.
The processor will not silently choose a different acquisition just because it is nearby.

The SAR band is not radiometrically calibrated. The threshold is calculated
automatically for each scene, and a confidence flag indicates the quality
of the water/land separation.
"""

import logging
import math
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple

import httpx
import numpy as np

logger = logging.getLogger(__name__)

PC_STAC_SEARCH = "https://planetarycomputer.microsoft.com/api/stac/v1/search"
PC_SAS_TOKEN = "https://planetarycomputer.microsoft.com/api/sas/v1/token/{collection}"
PC_COLLECTION = "sentinel-1-grd"

TARGET_WIDTH_PX = 1800
MIN_PIXELS_IN_LAKE_AREA = 500

# Strict matching tolerance.
# This prevents scenes acquired seconds apart from being confused.
ACQUISITION_MATCH_TOLERANCE_SECONDS = 2


class ProcessingError(Exception):
    """A readable reason why a scene could not be processed."""


def _parse_iso(value: str) -> datetime:
    """Parse an ISO timestamp and normalize it to UTC."""

    if not value:
        raise ProcessingError("Missing acquisition timestamp.")

    try:
        s = value.strip().replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)

        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        return dt.astimezone(timezone.utc)

    except (ValueError, TypeError) as exc:
        raise ProcessingError(
            f"Invalid acquisition timestamp: {value}"
        ) from exc


def _normalize_platform(value: Optional[str]) -> Optional[str]:
    """Normalize Sentinel platform names for comparison."""

    if not value:
        return None

    value = str(value).strip().lower().replace(" ", "")

    aliases = {
        "sentinel-1a": "sentinel-1a",
        "sentinel-1b": "sentinel-1b",
        "sentinel-1c": "sentinel-1c",
        "sentinel-1d": "sentinel-1d",
        "sentinel1a": "sentinel-1a",
        "sentinel1b": "sentinel-1b",
        "sentinel1c": "sentinel-1c",
        "sentinel1d": "sentinel-1d",
    }

    return aliases.get(value, value)


def _find_planetary_item(
    client: httpx.Client,
    acquired_iso: str,
    platform: Optional[str],
    bbox: Sequence[float],
) -> Dict[str, Any]:
    """
    Find the matching Sentinel-1 acquisition on Planetary Computer.

    Only items whose acquisition timestamp is within the strict tolerance
    are accepted. A nearby but different acquisition is not substituted.
    """

    target_time = _parse_iso(acquired_iso)

    tolerance = ACQUISITION_MATCH_TOLERANCE_SECONDS

    start_time = target_time - timedelta(seconds=tolerance)
    end_time = target_time + timedelta(seconds=tolerance)

    window = (
        f"{start_time.strftime('%Y-%m-%dT%H:%M:%SZ')}/"
        f"{end_time.strftime('%Y-%m-%dT%H:%M:%SZ')}"
    )

    logger.info(
        "Searching Planetary Computer for acquisition %s; window=%s",
        target_time.isoformat(),
        window,
    )

    try:
        resp = client.post(
            PC_STAC_SEARCH,
            json={
                "collections": [PC_COLLECTION],
                "bbox": list(bbox),
                "datetime": window,
                "limit": 20,
            },
        )

        resp.raise_for_status()

    except httpx.HTTPError as exc:
        raise ProcessingError(
            f"Could not search Microsoft Planetary Computer: {exc}"
        ) from exc

    items = resp.json().get("features", [])

    if not items:
        raise ProcessingError(
            "No Sentinel-1 acquisition was found on Microsoft Planetary "
            "Computer within the allowed 2-second matching window. "
            "The requested scene may not yet be available in this catalog."
        )

    wanted_platform = _normalize_platform(platform)

    matching_items = []

    for item in items:
        properties = item.get("properties", {})

        item_datetime = properties.get("datetime")

        if not item_datetime:
            continue

        try:
            item_time = _parse_iso(item_datetime)
        except ProcessingError:
            continue

        time_difference = abs(
            (item_time - target_time).total_seconds()
        )

        # Reject any acquisition outside the strict time tolerance.
        if time_difference > tolerance:
            continue

        item_platform = _normalize_platform(
            properties.get("platform")
        )

        # If a platform was requested, it must match.
        if wanted_platform and item_platform:
            if item_platform != wanted_platform:
                continue

        elif wanted_platform and not item_platform:
            logger.warning(
                "Planetary Computer item %s has no platform metadata.",
                item.get("id"),
            )
            continue

        matching_items.append(
            (
                time_difference,
                item,
            )
        )

    if not matching_items:
        raise ProcessingError(
            "Planetary Computer returned Sentinel-1 items, but none "
            "matched the requested acquisition time and platform. "
            "No other scene was substituted."
        )

    matching_items.sort(
        key=lambda entry: entry[0]
    )

    best_difference, best_item = matching_items[0]

    logger.info(
        "Matched Planetary Computer item %s; time difference=%.3f seconds",
        best_item.get("id"),
        best_difference,
    )

    return best_item


def _signed_href(
    client: httpx.Client,
    href: str,
) -> str:
    """Obtain a temporary Planetary Computer download URL."""

    try:
        resp = client.get(
            PC_SAS_TOKEN.format(
                collection=PC_COLLECTION
            )
        )

        resp.raise_for_status()

    except httpx.HTTPError as exc:
        raise ProcessingError(
            f"Could not obtain Planetary Computer access token: {exc}"
        ) from exc

    token = resp.json().get("token")

    if not token:
        raise ProcessingError(
            "Planetary Computer did not return a download token."
        )

    return f"{href}{'&' if '?' in href else '?'}{token}"


def _read_decimated(
    href: str,
) -> Tuple[
    np.ndarray,
    int,
    int,
    List[Tuple[float, float, float, float]]
]:
    """Read a reduced-resolution radar image and its ground control points."""

    try:
        import rasterio
        from rasterio.enums import Resampling

    except ImportError as exc:
        raise ProcessingError(
            "The 'rasterio' package is not installed. "
            "Run: pip install rasterio"
        ) from exc

    env = {
        "GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR",
        "CPL_VSIL_CURL_ALLOWED_EXTENSIONS": ".tif,.tiff",
        "GDAL_HTTP_MAX_RETRY": "3",
        "GDAL_HTTP_RETRY_DELAY": "2",
    }

    try:
        with rasterio.Env(**env):

            with rasterio.open(href) as src:

                height, width = src.height, src.width

                gcps, _ = src.gcps

                if gcps:

                    gcp_list = [
                        (
                            float(g.col),
                            float(g.row),
                            float(g.x),
                            float(g.y),
                        )
                        for g in gcps
                    ]

                elif (
                    src.crs is not None
                    and src.crs.is_geographic
                ):

                    transform = src.transform

                    gcp_list = []

                    for col, row in (
                        (0, 0),
                        (width, 0),
                        (0, height),
                        (width, height),
                    ):

                        x, y = transform * (col, row)

                        gcp_list.append(
                            (
                                float(col),
                                float(row),
                                float(x),
                                float(y),
                            )
                        )

                else:

                    raise ProcessingError(
                        "The radar image has no usable ground control points "
                        "or geographic transform to locate pixels."
                    )

                scale = max(
                    1.0,
                    width / TARGET_WIDTH_PX,
                )

                out_w = max(
                    1,
                    int(width / scale),
                )

                out_h = max(
                    1,
                    int(height / scale),
                )

                data = src.read(
                    1,
                    out_shape=(out_h, out_w),
                    resampling=Resampling.average,
                ).astype("float32")

    except ProcessingError:
        raise

    except Exception as exc:
        raise ProcessingError(
            f"Could not read the Sentinel-1 raster: {exc}"
        ) from exc

    if data.size == 0:
        raise ProcessingError(
            "The downloaded radar image contains no pixels."
        )

    return (
        data,
        height,
        width,
        gcp_list,
    )


def analyze_scene_array(
    data: np.ndarray,
    full_height: int,
    full_width: int,
    gcps: Sequence[
        Tuple[float, float, float, float]
    ],
    bbox: Sequence[float],
) -> Dict[str, Any]:
    """
    Pure-numpy SAR water classification.

    data is the decimated radar amplitude band.
    """

    if data.ndim != 2:
        raise ProcessingError(
            "The radar image must be a two-dimensional array."
        )

    if len(bbox) != 4:
        raise ProcessingError(
            "The Tonle Sap bounding box must contain four coordinates."
        )

    if len(gcps) < 3:
        raise ProcessingError(
            "Not enough ground control points to geolocate the scene."
        )

    if full_height <= 0 or full_width <= 0:
        raise ProcessingError(
            "Invalid original raster dimensions."
        )

    g = np.asarray(
        gcps,
        dtype="float64",
    )

    design = np.column_stack([
        np.ones(len(g)),
        g[:, 0],
        g[:, 1],
    ])

    (a0, a1, a2), *_ = np.linalg.lstsq(
        design,
        g[:, 2],
        rcond=None,
    )

    (b0, b1, b2), *_ = np.linalg.lstsq(
        design,
        g[:, 3],
        rcond=None,
    )

    out_h, out_w = data.shape

    cols = (
        np.arange(out_w) + 0.5
    ) * (
        full_width / out_w
    )

    rows = (
        np.arange(out_h) + 0.5
    ) * (
        full_height / out_h
    )

    col_grid, row_grid = np.meshgrid(
        cols,
        rows,
    )

    lon = (
        a0
        + a1 * col_grid
        + a2 * row_grid
    )

    lat = (
        b0
        + b1 * col_grid
        + b2 * row_grid
    )

    min_lon, min_lat, max_lon, max_lat = bbox

    valid = (
        np.isfinite(data)
        & (data > 0)
    )

    inside = (
        (lon >= min_lon)
        & (lon <= max_lon)
        & (lat >= min_lat)
        & (lat <= max_lat)
    )

    selected = valid & inside

    selected_count = int(selected.sum())

    if selected_count < MIN_PIXELS_IN_LAKE_AREA:
        raise ProcessingError(
            "This scene does not cover enough of the Tonle Sap area. "
            "There are too few valid radar pixels inside the selected region."
        )

    latitude_center = float(
        np.mean(lat[selected])
    )

    km_per_degree_lon = (
        111.320
        * math.cos(math.radians(latitude_center))
    )

    km_per_degree_lat = 110.574

    km2_full_pixel = abs(
        a1 * b2 - a2 * b1
    ) * km_per_degree_lon * km_per_degree_lat

    km2_pixel = (
        km2_full_pixel
        * (full_height / out_h)
        * (full_width / out_w)
    )

    if not np.isfinite(km2_pixel) or km2_pixel <= 0:
        raise ProcessingError(
            "Could not calculate a valid ground area for the radar pixels."
        )

    values = np.log10(
        data[selected]
    )

    if values.size < MIN_PIXELS_IN_LAKE_AREA:
        raise ProcessingError(
            "Not enough valid radar measurements for water classification."
        )

    if not np.all(np.isfinite(values)):
        values = values[np.isfinite(values)]

    if values.size < MIN_PIXELS_IN_LAKE_AREA:
        raise ProcessingError(
            "Too few finite radar measurements remain after filtering."
        )

    hist, edges = np.histogram(
        values,
        bins=256,
    )

    centers = (
        edges[:-1] + edges[1:]
    ) / 2.0

    hist = hist.astype("float64")

    weights_background = np.cumsum(hist)

    weights_foreground = (
        weights_background[-1] - weights_background
    )

    means_cumulative = np.cumsum(
        hist * centers
    )

    mean_background = (
        means_cumulative
        / np.maximum(weights_background, 1)
    )

    mean_foreground = (
        means_cumulative[-1] - means_cumulative
    ) / np.maximum(weights_foreground, 1)

    between_class_variance = (
        weights_background
        * weights_foreground
        * (mean_background - mean_foreground) ** 2
    )

    threshold_index = int(
        np.argmax(between_class_variance)
    )

    threshold_log = float(
        centers[threshold_index]
    )

    total_variance = float(
        values.var()
    )

    separation = (
        float(
            between_class_variance[threshold_index]
            / (
                weights_background[-1] ** 2
                * total_variance
            )
        )
        if total_variance > 0
        else 0.0
    )

    safe_data = np.where(
        np.isfinite(data) & (data > 0),
        data,
        1.0,
    )

    water = (
        selected
        & (
            np.log10(safe_data)
            < threshold_log
        )
    )

    water_km2 = float(
        water.sum() * km2_pixel
    )

    coverage_km2 = float(
        selected_count * km2_pixel
    )

    fraction = (
        water_km2 / coverage_km2
        if coverage_km2 > 0
        else 0.0
    )

    confidence = (
        "good"
        if (
            separation >= 0.5
            and 0.005 <= fraction <= 0.85
        )
        else "low"
    )

    return {
        "water_extent_km2": round(
            water_km2,
            1,
        ),

        "covered_area_km2": round(
            coverage_km2,
            1,
        ),

        "water_fraction": round(
            fraction,
            4,
        ),

        "threshold_amplitude": round(
            10 ** threshold_log,
            2,
        ),

        "class_separation": round(
            separation,
            3,
        ),

        "confidence": confidence,

        "pixel_km2": round(
            float(km2_pixel),
            5,
        ),

        "method": (
            "Otsu threshold on SAR backscatter "
            "(decimated GRD, uncalibrated)"
        ),
    }


def process_scene(
    acquired_iso: str,
    platform: Optional[str],
    bbox: Sequence[float],
) -> Dict[str, Any]:
    """
    Process one Sentinel-1 acquisition.

    This function is blocking and should be run in a worker thread.

    Returns the water-extent result dictionary.
    """

    with httpx.Client(
        timeout=httpx.Timeout(
            connect=10.0,
            read=60.0,
            write=10.0,
            pool=10.0,
        ),
        follow_redirects=True,
    ) as client:

        item = _find_planetary_item(
            client,
            acquired_iso,
            platform,
            bbox,
        )

        assets = item.get(
            "assets",
            {},
        )

        band = (
            "vv"
            if "vv" in assets
            else "vh"
            if "vh" in assets
            else None
        )

        if band is None:
            raise ProcessingError(
                "The matched scene has no VV or VH band to read."
            )

        asset = assets.get(band, {})

        asset_href = asset.get("href")

        if not asset_href:
            raise ProcessingError(
                f"The matched scene's {band.upper()} asset has no download URL."
            )

        href = _signed_href(
            client,
            asset_href,
        )

    data, height, width, gcps = _read_decimated(
        href
    )

    result = analyze_scene_array(
        data,
        height,
        width,
        gcps,
        bbox,
    )

    result.update({
        "source": "Microsoft Planetary Computer",

        "band": band.upper(),

        "item_id": item.get("id"),

        "matched_acquisition_datetime": (
            item.get("properties", {}).get("datetime")
        ),

        "requested_acquisition_datetime": acquired_iso,

        "processed_at": datetime.now(
            timezone.utc
        ).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        ),
    })

    return result
