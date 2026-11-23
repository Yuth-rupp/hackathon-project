"""
FloodPulse AI - Satellite catalog helpers (shared by the API router and the scheduler).

Turns raw Copernicus STAC features into a clean scene dict, stores scenes
without duplicates, and reads them back from the local database.

Two different "times" matter for satellite data, and both are kept:
  * acquisition_date - when the satellite actually imaged the ground (UTC)
  * published_at     - when the scene became available in the Copernicus catalog
"""

import json
import re

from datetime import datetime, timezone

from typing import Any, Dict, List, Optional

import aiosqlite


def parse_dt(value: Any) -> Optional[datetime]:
    """Parse an ISO-8601 string (with 'Z' or offset) into an aware UTC datetime."""

    if not value:
        return None

    s = str(value).strip()

    if s.endswith("Z"):
        s = s[:-1] + "+00:00"

    s = re.sub(
        r"(\.\d{6})\d+",
        r"\1",
        s,
    )

    try:
        dt = datetime.fromisoformat(s)

    except ValueError:
        return None

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    return dt.astimezone(timezone.utc)


def iso_utc(
    dt: Optional[datetime],
) -> Optional[str]:

    if not dt:
        return None

    return dt.astimezone(
        timezone.utc
    ).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def _pretty_platform(raw: Any) -> str:

    s = str(raw or "sentinel-1")

    if s.lower().startswith("sentinel-1"):

        return (
            "Sentinel-1"
            + s[len("sentinel-1"):].upper()
        )

    return s


def _bbox_from_geometry(
    geometry: Dict[str, Any],
) -> Optional[List[float]]:

    xs: List[float] = []
    ys: List[float] = []

    def walk(node: Any) -> None:

        if isinstance(node, (list, tuple)):

            if (
                len(node) >= 2
                and all(
                    isinstance(v, (int, float))
                    for v in node[:2]
                )
            ):

                xs.append(float(node[0]))
                ys.append(float(node[1]))

            else:

                for child in node:
                    walk(child)

    walk(
        (geometry or {}).get(
            "coordinates",
            [],
        )
    )

    return (
        [
            min(xs),
            min(ys),
            max(xs),
            max(ys),
        ]
        if xs
        else None
    )


def parse_stac_feature(
    feature: Dict[str, Any],
    collection: str,
) -> Optional[Dict[str, Any]]:

    """
    Normalize one STAC feature.

    Returns None if it has no usable acquisition time.
    """

    props = feature.get("properties") or {}

    assets = feature.get("assets") or {}

    links = feature.get("links") or []

    geometry = feature.get("geometry") or {}

    acq = parse_dt(
        props.get("datetime")
        or props.get("start_datetime")
    )

    if acq is None:
        return None

    scene_id = feature.get("id")

    published = parse_dt(
        props.get("published")
        or props.get("created")
        or props.get("updated")
    )

    stac_url = next(
        (
            link.get("href")
            for link in links
            if (
                link.get("rel") == "self"
                and link.get("href")
            )
        ),
        None,
    )

    if not stac_url and scene_id:

        stac_url = (
            "https://stac.dataspace.copernicus.eu/v1/"
            f"collections/{collection}/items/{scene_id}"
        )

    thumb = (
        assets.get("thumbnail")
        or assets.get("quicklook")
        or {}
    ).get(
        "href",
        "",
    )

    bbox = feature.get("bbox")

    if isinstance(bbox, list) and len(bbox) == 6:

        bbox = [
            bbox[0],
            bbox[1],
            bbox[3],
            bbox[4],
        ]

    if not (
        isinstance(bbox, list)
        and len(bbox) == 4
    ):

        bbox = _bbox_from_geometry(
            geometry
        )

    orbit = (
        props.get("sat:orbit_state")
        or props.get("sat:orbit_direction")
    )

    pols = props.get("sar:polarizations")

    rel_orbit = props.get(
        "sat:relative_orbit"
    )

    platform = _pretty_platform(
        props.get("platform")
        or props.get("constellation")
    )

    return {

        "scene_id": scene_id,

        "satellite": f"{platform} SAR",

        "platform": platform,

        "acquisition_date": iso_utc(acq),

        "published_at": iso_utc(published),

        "collection": collection,

        "orbit_state": (
            str(orbit).lower()
            if orbit
            else None
        ),

        "relative_orbit": (
            int(rel_orbit)
            if isinstance(rel_orbit, (int, float))
            else None
        ),

        "instrument_mode": props.get(
            "sar:instrument_mode",
            "IW",
        ),

        "polarization": (
            "+".join(pols)
            if isinstance(pols, list) and pols
            else None
        ),

        "stac_url": stac_url,

        "thumbnail_url": thumb,

        "bbox": bbox,

        "geometry": geometry,
    }


async def store_scene(
    db: aiosqlite.Connection,
    scene: Dict[str, Any],
) -> bool:

    """
    Insert a parsed scene unless it is already stored.

    Returns True if newly inserted.

    The caller is responsible for db.commit().
    """

    cursor = await db.execute(
        """
        SELECT id

        FROM satellite_acquisitions

        WHERE (
            stac_url IS NOT NULL
            AND stac_url = ?
        )

        OR (
            satellite = ?
            AND acquisition_date = ?
            AND COALESCE(collection, '') = ?
        )

        LIMIT 1
        """,

        (
            scene["stac_url"],
            scene["satellite"],
            scene["acquisition_date"],
            scene["collection"] or "",
        ),
    )

    if await cursor.fetchone():
        return False

    await db.execute(
        """
        INSERT INTO satellite_acquisitions (

            satellite,
            acquisition_date,
            collection,
            orbit_state,
            instrument_mode,
            bbox_geojson,
            cloud_cover,
            stac_url,
            thumbnail_url,
            processed,
            water_extent_km2,
            metadata_json

        )

        VALUES (
            ?, ?, ?, ?, ?, ?, 0.0, ?, ?, 0, NULL, ?
        )
        """,

        (
            scene["satellite"],

            scene["acquisition_date"],

            scene["collection"],

            scene["orbit_state"],

            scene["instrument_mode"],

            json.dumps(
                scene.get("geometry") or {}
            ),

            scene["stac_url"],

            scene["thumbnail_url"],

            json.dumps({

                "scene_id": scene["scene_id"],

                "platform": scene["platform"],

                "published": scene["published_at"],

                "relative_orbit": scene["relative_orbit"],

                "polarizations": scene["polarization"],

                "bbox": scene["bbox"],

            }),
        ),
    )

    return True


def row_to_scene(
    row: Any,
) -> Dict[str, Any]:

    """
    Convert a satellite_acquisitions row
    into SatelliteScene fields (cache read).
    """

    try:

        md = json.loads(
            row["metadata_json"] or "{}"
        )

    except (TypeError, ValueError):

        md = {}

    pols = (
        md.get("polarizations")
        or md.get("sar:polarizations")
    )

    if isinstance(pols, list):

        pols = "+".join(pols)

    scene_id = (
        md.get("scene_id")
        or md.get("stac_id")
    )

    if (
        not scene_id
        and row["stac_url"]
    ):

        scene_id = (
            str(row["stac_url"])
            .rstrip("/")
            .split("/")[-1]
        )

    bbox = md.get("bbox")

    if not bbox:

        try:

            bbox = _bbox_from_geometry(
                json.loads(
                    row["bbox_geojson"] or "{}"
                )
            )

        except (TypeError, ValueError):

            bbox = None

    return {

        "id": row["id"],

        "scene_id": scene_id,

        "satellite": row["satellite"],

        "platform": md.get("platform"),

        "acquisition_date": (
            iso_utc(
                parse_dt(row["acquisition_date"])
            )
            or row["acquisition_date"]
        ),

        "published_at": iso_utc(
            parse_dt(
                md.get("published")
                or md.get("created")
                or md.get("updated")
            )
        ),

        "collection": row["collection"],

        "orbit_state": (
            row["orbit_state"].lower()
            if row["orbit_state"]
            else None
        ),

        "relative_orbit": (
            md.get("relative_orbit")
            or md.get("sat:relative_orbit")
        ),

        "instrument_mode": row["instrument_mode"],

        "polarization": pols,

        "cloud_cover": row["cloud_cover"],

        "water_extent_km2": row["water_extent_km2"],

        "stac_url": row["stac_url"],

        "thumbnail_url": row["thumbnail_url"],

        "bbox": bbox,

        "processed": bool(row["processed"]),
    }