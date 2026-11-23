"""
FloodPulse AI - External Data Connectors
Standardized connectors for Open-Meteo, Copernicus STAC, JRC Surface Water,
Open Development Cambodia, Mekong River Commission, and NASA FIRMS.
"""

from app.connectors.base import BaseConnector, ConnectorError, RateLimitError
from app.connectors.open_meteo import OpenMeteoConnector
from app.connectors.copernicus import CopernicusSTACConnector
from app.connectors.jrc import JRCConnector
from app.connectors.odc import ODCConnector
from app.connectors.mrc import MRCConnector
from app.connectors.firms import FIRMSConnector

__all__ = [
    "BaseConnector",
    "ConnectorError",
    "RateLimitError",
    "OpenMeteoConnector",
    "CopernicusSTACConnector",
    "JRCConnector",
    "ODCConnector",
    "MRCConnector",
    "FIRMSConnector",
]
