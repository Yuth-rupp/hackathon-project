"""
FloodPulse AI - Stations and Hydrological Telemetry Router
Endpoints for MRC gauging stations, real-time water levels, and monitoring locations.
"""

from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query
from app.database import fetch_all, fetch_one, execute_query
from app.models import (
    StationResponse,
    WaterLevelReading,
    WaterLevelCreateRequest,
    MonitoringLocationResponse,
    ApiResponse
)

router = APIRouter(tags=["Stations & Hydrology"])


@router.get("/stations", response_model=List[StationResponse])
async def list_stations(is_active: Optional[bool] = Query(None, description="Filter by active status")):
    """
    List all hydrological and lake gauging stations around Tonle Sap Lake,
    including latest water level and alarm/flood danger thresholds.
    """
    query = """
    SELECT s.*,
           (SELECT wl.value FROM water_levels wl WHERE wl.station_id = s.id ORDER BY wl.timestamp DESC LIMIT 1) as latest_water_level,
           (SELECT wl.timestamp FROM water_levels wl WHERE wl.station_id = s.id ORDER BY wl.timestamp DESC LIMIT 1) as latest_reading_time
    FROM stations s
    """
    params = ()
    if is_active is not None:
        query += " WHERE s.is_active = ?"
        params = (1 if is_active else 0,)

    query += " ORDER BY s.id ASC"
    rows = await fetch_all(query, params)

    results = []
    for row in rows:
        r = dict(row)
        val = r.get("latest_water_level")
        alarm = r.get("alarm_level")
        flood = r.get("flood_level")
        status = "normal"
        if val is not None:
            if flood and val >= flood:
                status = "flood"
            elif alarm and val >= alarm:
                status = "alarm"
        r["status"] = status
        r["is_active"] = bool(r.get("is_active", 1))
        results.append(StationResponse(**r))

    return results


@router.get("/stations/{id_or_code}", response_model=StationResponse)
async def get_station(id_or_code: str):
    """
    Retrieve single station details by either database ID or MRC station code.
    """
    if id_or_code.isdigit():
        row = await fetch_one(
            """
            SELECT s.*,
                   (SELECT wl.value FROM water_levels wl WHERE wl.station_id = s.id ORDER BY wl.timestamp DESC LIMIT 1) as latest_water_level,
                   (SELECT wl.timestamp FROM water_levels wl WHERE wl.station_id = s.id ORDER BY wl.timestamp DESC LIMIT 1) as latest_reading_time
            FROM stations s WHERE s.id = ? OR s.code = ?
            """,
            (int(id_or_code), id_or_code)
        )
    else:
        row = await fetch_one(
            """
            SELECT s.*,
                   (SELECT wl.value FROM water_levels wl WHERE wl.station_id = s.id ORDER BY wl.timestamp DESC LIMIT 1) as latest_water_level,
                   (SELECT wl.timestamp FROM water_levels wl WHERE wl.station_id = s.id ORDER BY wl.timestamp DESC LIMIT 1) as latest_reading_time
            FROM stations s WHERE s.code = ?
            """,
            (id_or_code,)
        )

    if not row:
        raise HTTPException(status_code=404, detail=f"Station '{id_or_code}' not found.")

    r = dict(row)
    val = r.get("latest_water_level")
    alarm = r.get("alarm_level")
    flood = r.get("flood_level")
    status = "normal"
    if val is not None:
        if flood and val >= flood:
            status = "flood"
        elif alarm and val >= alarm:
            status = "alarm"
    r["status"] = status
    r["is_active"] = bool(r.get("is_active", 1))
    return StationResponse(**r)


@router.get("/stations/{id_or_code}/water-levels", response_model=List[WaterLevelReading])
async def get_station_water_levels(
    id_or_code: str,
    limit: int = Query(50, ge=1, le=500, description="Max readings to return")
):
    """
    Retrieve chronological water level telemetry history for a specific station.
    """
    station = await fetch_one("SELECT id, code, name FROM stations WHERE id = ? OR code = ?", (id_or_code, id_or_code))
    if not station:
        raise HTTPException(status_code=404, detail=f"Station '{id_or_code}' not found.")

    rows = await fetch_all(
        """
        SELECT wl.*, s.code as station_code, s.name as station_name
        FROM water_levels wl
        JOIN stations s ON s.id = wl.station_id
        WHERE wl.station_id = ?
        ORDER BY wl.timestamp DESC
        LIMIT ?
        """,
        (station["id"], limit)
    )
    return [WaterLevelReading(**dict(r)) for r in rows]


@router.post("/water-levels", response_model=ApiResponse)
async def create_water_level_reading(req: WaterLevelCreateRequest):
    """
    Record a new water level observation for a station.
    """
    station = await fetch_one("SELECT id, name, alarm_level, flood_level FROM stations WHERE id = ?", (req.station_id,))
    if not station:
        raise HTTPException(status_code=404, detail=f"Station ID {req.station_id} not found.")

    query = """
    INSERT INTO water_levels (station_id, timestamp, value, unit, data_source, quality_flag)
    VALUES (?, ?, ?, ?, ?, ?)
    """
    new_id = await execute_query(
        query,
        (req.station_id, req.timestamp, req.value, req.unit, req.data_source, req.quality_flag)
    )

    return ApiResponse(
        success=True,
        message=f"Water level reading {new_id} recorded for station '{station['name']}'",
        data={"id": new_id, "value": req.value, "station": station["name"]}
    )


@router.get("/monitoring-locations", response_model=List[MonitoringLocationResponse])
async def list_monitoring_locations():
    """
    List all 5 core monitored municipal and provincial centers around Tonle Sap Lake:
    Siem Reap, Battambang, Pursat, Kampong Thom, Kampong Chhnang.
    """
    rows = await fetch_all("SELECT * FROM monitoring_locations ORDER BY id ASC")
    return [MonitoringLocationResponse(**dict(r)) for r in rows]
