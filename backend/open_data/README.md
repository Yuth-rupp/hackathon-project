# FloodPulse AI - Open Data

Generated: 2026-11-25 01:25 UTC

Real data used by the FloodPulse AI flood monitoring system for the
Tonle Sap Basin, Cambodia. Sample rows are excluded.

## Files

| File | Content | Source | Rows |
|---|---|---|---|
| `monitoring_locations.csv` | Monitoring locations (five Tonle Sap provinces) | Project configuration | 5 |
| `weather_hourly.csv` | Hourly rainfall, soil moisture and weather | Open-Meteo (CC BY 4.0) | 5052 |
| `river_discharge.csv` | River discharge (GloFAS via Open-Meteo Flood API) | Open-Meteo Flood API / GloFAS (CC BY 4.0) | 768 |
| `satellite_acquisitions.csv` | Satellite scene metadata | Copernicus Sentinel-1 (STAC catalogue) | 21 |
| `risk_assessments.csv` | FloodPulse AI risk assessments (project output) | Calculated by this project from the data above | 418 |

## Data sources and licences

| Source | Used for | Licence / access |
|---|---|---|
| [Open-Meteo](https://open-meteo.com/) | Rainfall, soil moisture, weather | CC BY 4.0, no key, free for non-commercial use |
| [Open-Meteo Flood API](https://open-meteo.com/en/docs/flood-api) (GloFAS) | River discharge forecast | CC BY 4.0, no key |
| [Copernicus Sentinel-1](https://dataspace.copernicus.eu/) | Radar satellite scenes | Free and open, check the Copernicus terms |
| [JRC Global Surface Water](https://global-surface-water.appspot.com/) | Surface water map layer | Free, cite Pekel et al. (2016) |
| [Open Development Cambodia](https://opendevelopmentcambodia.net/) | Cambodian reference datasets | Licence is set per dataset |
| [OpenStreetMap](https://www.openstreetmap.org/copyright) | Street map tiles | ODbL, credit contributors |

Not included in this export: Mekong River Commission gauge data (access
requires a token), and sample baseline rows created on first launch.


## Attribution

Weather data by [Open-Meteo.com](https://open-meteo.com/).
