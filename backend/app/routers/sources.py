"""
FloodPulse AI - Data Sources & Connector Health Router
Monitors live uptime, license provenance, and synchronization status of all external connectors.
"""

from typing import List
from fastapi import APIRouter, HTTPException
from app.database import fetch_all, fetch_one
from app.models import DataSourceStatusResponse

router = APIRouter(tags=["Data Sources & Health"])


@router.get("/data-sources", response_model=List[DataSourceStatusResponse])
async def list_data_sources():
    """
    List all external research, satellite, and governmental data connectors:
    Open-Meteo Weather, GloFAS River Discharge, Copernicus Sentinel-1 STAC,
    JRC Global Surface Water, Open Development Cambodia, MRC Hydromet, NASA FIRMS.
    """
    rows = await fetch_all("SELECT * FROM data_sources ORDER BY id ASC")
    return [DataSourceStatusResponse(**dict(r)) for r in rows]


@router.get("/data-sources/{source_id}", response_model=DataSourceStatusResponse)
async def get_data_source(source_id: int):
    """
    Get detailed connectivity metrics and latest errors for a specific data source.
    """
    row = await fetch_one("SELECT * FROM data_sources WHERE id = ?", (source_id,))
    if not row:
        raise HTTPException(status_code=404, detail=f"Data source ID {source_id} not found.")
    return DataSourceStatusResponse(**dict(row))
