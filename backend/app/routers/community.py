"""
FloodPulse AI - Community Resilience & Provincial Vulnerability API Router
Provides comprehensive profiles, critical infrastructure inventories, and historical flood records
for the 5 provinces surrounding Tonle Sap Lake.
"""

import json
import logging
from typing import Dict, Any, List, Optional

import aiosqlite
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.database import get_db
from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/community", tags=["Community & Provinces"])


class InfrastructureItem(BaseModel):
    name: str
    name_km: str
    type: str  # e.g., "safe_mound", "evacuation_center", "health_center", "school", "bridge", "embankment"
    capacity_people: Optional[int]
    lat: float
    lon: float
    elevation_m: float
    is_safe_above_alarm: bool = True


class ProvinceProfile(BaseModel):
    id: int
    name: str
    name_km: str
    province_code: str
    population: int
    vulnerable_communes_count: int
    area_km2: float
    elevation_m: float
    distance_to_lake_km: float
    topography: str
    historical_flood_risk_score: float
    critical_infrastructure: List[InfrastructureItem]
    recent_flood_count: int
    current_risk_category: str
    current_risk_probability: float


class FloodEventRecord(BaseModel):
    id: int
    event_date: str
    end_date: Optional[str]
    province: str
    district: Optional[str]
    commune: Optional[str]
    deaths: int
    affected_people: int
    houses_damaged: int
    houses_destroyed: int
    crop_area_ha: float
    economic_loss_usd: float
    data_source: str
    notes: Optional[str]


# Rich domain data for community infrastructure around Tonle Sap
COMMUNITY_PROVINCE_METRICS: Dict[str, Dict[str, Any]] = {
    "siem_reap": {
        "code": "KH-17",
        "population": 1014234,
        "vulnerable_communes": 24,
        "area_km2": 10299.0,
        "topography": "Alluvial floodplain extending from Kulen Mountains to northern shore of Tonle Sap Lake",
        "infrastructure": [
            {"name": "Chreav Safe Mound (Toul Sopheakpheap)", "name_km": "ទួលសុវត្ថិភាពជ្រាវ", "type": "safe_mound", "capacity_people": 2500, "lat": 13.310, "lon": 103.880, "elevation_m": 22.0},
            {"name": "Phnom Krom Community Shelter", "name_km": "ជម្រកសហគមន៍ភ្នំក្រោម", "type": "evacuation_center", "capacity_people": 1800, "lat": 13.285, "lon": 103.820, "elevation_m": 35.0},
            {"name": "Siem Reap Provincial Referral Hospital", "name_km": "មន្ទីរពេទ្យបង្អែកខេត្តសៀមរាប", "type": "health_center", "capacity_people": 500, "lat": 13.355, "lon": 103.855, "elevation_m": 19.5},
            {"name": "Puok River Diversion Spillway", "name_km": "ទំនប់បញ្ចៀសទឹកស្ទឹងពួក", "type": "embankment", "capacity_people": None, "lat": 13.410, "lon": 103.740, "elevation_m": 21.0}
        ]
    },
    "battambang": {
        "code": "KH-02",
        "population": 997169,
        "vulnerable_communes": 31,
        "area_km2": 11702.0,
        "topography": "Fertile river delta and low-gradient rice plains fed by Sangkae River discharging into Tonle Sap",
        "infrastructure": [
            {"name": "Wat Kor Disaster Evacuation Center", "name_km": "មជ្ឈមណ្ឌលជម្លៀសគ្រោះមហន្តរាយវត្តគរ", "type": "evacuation_center", "capacity_people": 3200, "lat": 13.070, "lon": 103.190, "elevation_m": 21.0},
            {"name": "Ek Phnom Safe Mound", "name_km": "ទួលសុវត្ថិភាពឯកភ្នំ", "type": "safe_mound", "capacity_people": 2000, "lat": 13.160, "lon": 103.180, "elevation_m": 19.5},
            {"name": "Battambang Sangkae River Protection Dike", "name_km": "ទំនប់ការពារទឹកជំនន់ស្ទឹងសង្កែ", "type": "embankment", "capacity_people": None, "lat": 13.105, "lon": 103.205, "elevation_m": 18.0},
            {"name": "Moung Ruessei Safe Mound", "name_km": "ទួលសុវត្ថិភាពមោងឫស្សី", "type": "safe_mound", "capacity_people": 1500, "lat": 12.790, "lon": 103.450, "elevation_m": 18.5}
        ]
    },
    "pursat": {
        "code": "KH-15",
        "population": 419952,
        "vulnerable_communes": 28,
        "area_km2": 12692.0,
        "topography": "Cardamom mountain foothills transitioning steeply into the southern Tonle Sap floodplain and Krakor flood delta",
        "infrastructure": [
            {"name": "Krakor Floating Community High Ground Mound", "name_km": "ទួលសុវត្ថិភាពក្រគរ", "type": "safe_mound", "capacity_people": 4000, "lat": 12.550, "lon": 104.180, "elevation_m": 17.5},
            {"name": "Pursat Town Pagoda Evacuation Complex", "name_km": "មជ្ឈមណ្ឌលសង្គ្រោះបន្ទាន់ក្រុងពោធិ៍សាត់", "type": "evacuation_center", "capacity_people": 2200, "lat": 12.535, "lon": 103.920, "elevation_m": 17.0},
            {"name": "Damnak Chheukrom Dam & Flood Sluice", "name_km": "ទំនប់ដំណាក់ឈើក្រម", "type": "embankment", "capacity_people": None, "lat": 12.450, "lon": 103.880, "elevation_m": 24.0}
        ]
    },
    "kampong_thom": {
        "code": "KH-06",
        "population": 677260,
        "vulnerable_communes": 35,
        "area_km2": 13814.0,
        "topography": "Expansive flat eastern floodplain drained by Stung Sen, the largest direct tributary basin of Tonle Sap",
        "infrastructure": [
            {"name": "Stueng Saen Safe Mound & Relief Station", "name_km": "ទួលសុវត្ថិភាពស្ទឹងសែន", "type": "safe_mound", "capacity_people": 3500, "lat": 12.715, "lon": 104.890, "elevation_m": 16.5},
            {"name": "Kampong Svay Secondary School Shelter", "name_km": "ជម្រកសាលាអនុវិទ្យាល័យកំពង់ស្វាយ", "type": "school", "capacity_people": 1600, "lat": 12.750, "lon": 104.820, "elevation_m": 15.0},
            {"name": "Stung Chinit Irrigation & Flood Regulator", "name_km": "សំណង់ការពារទឹកជំនន់ស្ទឹងជីនិត", "type": "embankment", "capacity_people": None, "lat": 12.520, "lon": 105.150, "elevation_m": 18.0}
        ]
    },
    "kampong_chhnang": {
        "code": "KH-04",
        "population": 525932,
        "vulnerable_communes": 38,
        "area_km2": 5521.0,
        "topography": "Low-lying bottleneck outlet where Tonle Sap Lake narrows into Tonle Sap River. Extremely sensitive to backwater pulse",
        "infrastructure": [
            {"name": "Boribor Safe Mound (Toul Sopheakpheap)", "name_km": "ទួលសុវត្ថិភាពបរិបូណ៌", "type": "safe_mound", "capacity_people": 4500, "lat": 12.420, "lon": 104.550, "elevation_m": 15.0},
            {"name": "Kampong Tralach Community Relief Hall", "name_km": "សាលាសហគមន៍កំពង់ត្រឡាច", "type": "evacuation_center", "capacity_people": 2000, "lat": 11.980, "lon": 104.720, "elevation_m": 13.5},
            {"name": "Kampong Chhnang Provincial Stadium Safe Site", "name_km": "ពហុកីឡដ្ឋានខេត្តកំពង់ឆ្នាំង", "type": "evacuation_center", "capacity_people": 5000, "lat": 12.250, "lon": 104.665, "elevation_m": 14.5}
        ]
    }
}


@router.get("/provinces", response_model=List[ProvinceProfile])
async def list_provinces(db: aiosqlite.Connection = Depends(get_db)) -> List[ProvinceProfile]:
    """
    List all 5 target provinces around Tonle Sap with vulnerability profiles and community safe sites.
    """
    cursor = await db.execute("SELECT id, name, name_km, province, elevation_m, distance_to_lake_km, flood_frequency_score FROM monitoring_locations")
    loc_rows = await cursor.fetchall()
    profiles = []

    for loc in loc_rows:
        loc_id = loc["id"]
        key = loc["name"].lower().replace(" ", "_")
        domain_info = COMMUNITY_PROVINCE_METRICS.get(key, COMMUNITY_PROVINCE_METRICS["siem_reap"])

        # Count historical flood events in this province
        e_cursor = await db.execute(
            "SELECT COUNT(*) as count FROM flood_events WHERE province LIKE ?",
            (f"%{loc['province']}%",)
        )
        e_row = await e_cursor.fetchone()
        flood_count = int(e_row["count"]) if e_row else 3

        # Latest risk assessment
        r_cursor = await db.execute(
            "SELECT risk_category, risk_probability FROM risk_assessments WHERE location_id = ? ORDER BY id DESC LIMIT 1",
            (loc_id,)
        )
        r_row = await r_cursor.fetchone()
        risk_cat = r_row["risk_category"] if r_row else "Low"
        risk_prob = float(r_row["risk_probability"]) if r_row else 15.0

        infra_items = [
            InfrastructureItem(**item) for item in domain_info["infrastructure"]
        ]

        profiles.append(ProvinceProfile(
            id=loc_id,
            name=loc["name"],
            name_km=loc["name_km"] or loc["name"],
            province_code=domain_info["code"],
            population=domain_info["population"],
            vulnerable_communes_count=domain_info["vulnerable_communes"],
            area_km2=domain_info["area_km2"],
            elevation_m=float(loc["elevation_m"] or 15.0),
            distance_to_lake_km=float(loc["distance_to_lake_km"] or 15.0),
            topography=domain_info["topography"],
            historical_flood_risk_score=float(loc["flood_frequency_score"] or 0.65),
            critical_infrastructure=infra_items,
            recent_flood_count=flood_count,
            current_risk_category=risk_cat,
            current_risk_probability=round(risk_prob, 1)
        ))

    return profiles


@router.get("/provinces/{province}", response_model=ProvinceProfile)
async def get_province_detail(
    province: str,
    db: aiosqlite.Connection = Depends(get_db)
) -> ProvinceProfile:
    """
    Retrieve comprehensive community vulnerability profile for a specific Tonle Sap province.
    """
    cursor = await db.execute(
        "SELECT id, name, name_km, province, elevation_m, distance_to_lake_km, flood_frequency_score FROM monitoring_locations WHERE LOWER(name) = LOWER(?) OR LOWER(province) = LOWER(?) OR id = ?",
        (province, province, province if province.isdigit() else -1)
    )
    loc = await cursor.fetchone()
    if not loc:
        raise HTTPException(status_code=404, detail=f"Province '{province}' not found.")

    key = loc["name"].lower().replace(" ", "_")
    domain_info = COMMUNITY_PROVINCE_METRICS.get(key, COMMUNITY_PROVINCE_METRICS["pursat"])

    e_cursor = await db.execute("SELECT COUNT(*) as count FROM flood_events WHERE province LIKE ?", (f"%{loc['province']}%",))
    e_row = await e_cursor.fetchone()
    flood_count = int(e_row["count"]) if e_row else 2

    r_cursor = await db.execute("SELECT risk_category, risk_probability FROM risk_assessments WHERE location_id = ? ORDER BY id DESC LIMIT 1", (loc["id"],))
    r_row = await r_cursor.fetchone()
    risk_cat = r_row["risk_category"] if r_row else "Low"
    risk_prob = float(r_row["risk_probability"]) if r_row else 15.0

    infra_items = [InfrastructureItem(**item) for item in domain_info["infrastructure"]]

    return ProvinceProfile(
        id=loc["id"],
        name=loc["name"],
        name_km=loc["name_km"] or loc["name"],
        province_code=domain_info["code"],
        population=domain_info["population"],
        vulnerable_communes_count=domain_info["vulnerable_communes"],
        area_km2=domain_info["area_km2"],
        elevation_m=float(loc["elevation_m"] or 15.0),
        distance_to_lake_km=float(loc["distance_to_lake_km"] or 15.0),
        topography=domain_info["topography"],
        historical_flood_risk_score=float(loc["flood_frequency_score"] or 0.65),
        critical_infrastructure=infra_items,
        recent_flood_count=flood_count,
        current_risk_category=risk_cat,
        current_risk_probability=round(risk_prob, 1)
    )


@router.get("/flood-history", response_model=List[FloodEventRecord])
async def list_flood_history(
    province: Optional[str] = Query(None, description="Filter by province name"),
    start_year: Optional[int] = Query(None, description="Start year filter"),
    end_year: Optional[int] = Query(None, description="End year filter"),
    db: aiosqlite.Connection = Depends(get_db)
) -> List[FloodEventRecord]:
    """
    Query historical Cambodia flood disaster archives (ODC / NCDM records from 2000 to present).
    """
    query = """
        SELECT id, event_date, end_date, province, district, commune,
               deaths, affected_people, houses_damaged, houses_destroyed,
               crop_area_ha, economic_loss_usd, data_source, notes
        FROM flood_events
    """
    conditions = []
    params: List[Any] = []

    if province:
        conditions.append("province LIKE ?")
        params.append(f"%{province}%")
    if start_year:
        conditions.append("substr(event_date, 1, 4) >= ?")
        params.append(str(start_year))
    if end_year:
        conditions.append("substr(event_date, 1, 4) <= ?")
        params.append(str(end_year))

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    query += " ORDER BY event_date DESC LIMIT 100"

    cursor = await db.execute(query, tuple(params))
    rows = await cursor.fetchall()

    return [
        FloodEventRecord(
            id=r["id"],
            event_date=r["event_date"] or "2020-10-15",
            end_date=r["end_date"],
            province=r["province"] or "Tonle Sap Basin",
            district=r["district"],
            commune=r["commune"],
            deaths=r["deaths"] or 0,
            affected_people=r["affected_people"] or 0,
            houses_damaged=r["houses_damaged"] or 0,
            houses_destroyed=r["houses_destroyed"] or 0,
            crop_area_ha=float(r["crop_area_ha"] or 0.0),
            economic_loss_usd=float(r["economic_loss_usd"] or 0.0),
            data_source=r["data_source"] or "NCDM/ODC",
            notes=r["notes"]
        )
        for r in rows
    ]
