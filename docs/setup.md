# FloodPulse AI — Setup Guide

## System Requirements

- **Node.js** 18.0+ (recommended: 20.x LTS)
- **npm** 9.0+
- **Python** 3.10+ (recommended: 3.12)
- **pip** 23.0+
- **Git** 2.0+

## Backend Setup

### 1. Create Virtual Environment

```bash
cd backend
python -m venv venv

# Activate (Windows)
venv\Scripts\activate

# Activate (Linux/Mac)
source venv/bin/activate
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` and configure:
- `DATABASE_URL` — SQLite path (default works)
- `TELEGRAM_BOT_TOKEN` — Optional, for alert delivery
- `TELEGRAM_CHAT_ID` — Optional, target chat for alerts
- `MRC_API_TOKEN` — Optional, if you have MRC PDIES credentials
- `FIRMS_API_KEY` — Optional, from https://firms.modaps.eosdis.nasa.gov/api/map_key/

### 4. Initialize Database

```bash
python -m app.data.seed
```

This creates the SQLite database, all tables, and seeds:
- 5 monitoring locations (provinces)
- 3 hydrological stations
- 7 data source records
- Historical flood events

### 5. Start Backend

```bash
uvicorn app.main:app --reload --port 8000
```

API documentation available at http://localhost:8000/docs

## Frontend Setup

### 1. Install Dependencies

```bash
cd frontend
npm install
```

### 2. Configure Environment

```bash
cp .env.example .env.local
```

Default `NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1` should work.

### 3. Start Development Server

```bash
npm run dev
```

Application available at http://localhost:3000

## Data Source Configuration

### Open-Meteo (Auto-configured)
No API key needed. Weather, flood discharge, and historical data fetch automatically.

### JRC Global Surface Water (Auto-configured)
Free tile service loads automatically in the map. No configuration needed.

### Copernicus STAC (Auto-configured for search)
Catalog search works without authentication. For downloading actual Sentinel-1 imagery, register at https://dataspace.copernicus.eu/

### MRC Data Services (Optional)
Contact MRC Secretariat (mrcs@mrcmekong.org) for PDIES API credentials. Set `MRC_API_TOKEN` in `.env`.

### NASA FIRMS (Optional)
Register for free API key at https://firms.modaps.eosdis.nasa.gov/api/map_key/. Set `FIRMS_API_KEY` in `.env`.

### Telegram Alerts (Optional)
1. Message @BotFather on Telegram to create a bot
2. Get the bot token
3. Add bot to your group/channel
4. Get the chat ID
5. Set `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` in `.env`

## Competition Demo Workflow

1. Open http://localhost:3000 — show landing page
2. Click "Explore Dashboard" — show main monitoring dashboard with Tonle Sap map
3. Click a station on the map — show real-time data panel
4. Navigate to Hydrology — show river discharge charts from GloFAS
5. Navigate to Weather — show current conditions and forecasts
6. Navigate to Satellite — search STAC catalog, show JRC water layers
7. Navigate to AI Risk — show risk assessments with factor breakdown
8. Navigate to Community — show province profiles and flood history
9. Navigate to Alerts — demonstrate alert creation and Telegram delivery
10. Navigate to Data Sources — show all source connections and health
11. Toggle language to Khmer — demonstrate bilingual interface
12. Toggle dark/light mode — demonstrate visual design
