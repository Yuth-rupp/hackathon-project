# 🌊 FloodPulse AI

**Turning Open Data into Smarter Flood Preparedness**

An AI-powered flood monitoring and early-warning platform transforming open environmental data into actionable flood preparedness intelligence for communities around Cambodia's Tonle Sap Lake.

## 🎯 Problem

Communities surrounding Tonle Sap Lake face seasonal flooding and changing hydrological conditions. Environmental information is distributed across multiple platforms, and users need an accessible way to understand local conditions, monitor changes, assess potential risks, and prepare.

## 💡 Solution

FloodPulse AI integrates hydrological observations, rainfall information, historical flood records, satellite imagery, and AI-powered analysis into one monitoring and community preparedness platform.

## 🗺️ Coverage

| Province | Khmer | Role |
|----------|-------|------|
| Siem Reap | សៀមរាប | Northern basin |
| Battambang | បាត់ដំបង | Western gateway |
| Pursat | ពោធិ៍សាត់ | Southwest sector |
| Kampong Thom | កំពង់ធំ | Eastern basin |
| Kampong Chhnang | កំពង់ឆ្នាំង | Southern outlet |

## 🏗️ Architecture

```
Frontend:  Next.js 14 + TypeScript + Tailwind CSS + Leaflet + Recharts
Backend:   Python FastAPI + Pydantic v2 + APScheduler
Database:  SQLite + GeoJSON + GeoTIFF
ML:        scikit-learn (Logistic Regression, Random Forest)
Alerts:    Telegram Bot API
i18n:      English + Khmer
```

## 🚀 Quick Start

### Prerequisites
- Node.js 18+ and npm
- Python 3.10+ and pip

### 1. Backend Setup

```bash
cd backend
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # Linux/Mac

pip install -r requirements.txt
cp .env.example .env

# Initialize database and seed data
python -m app.data.seed

# Start backend
uvicorn app.main:app --reload --port 8000
```

### 2. Frontend Setup

```bash
cd frontend
npm install

# Start dev server
npm run dev
```

### 3. Access

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs

## 📊 Data Sources

| Source | Auth Required | Status |
|--------|:---:|--------|
| Open-Meteo Weather | No | ✅ Ready |
| Open-Meteo Flood API (GloFAS) | No | ✅ Ready |
| Copernicus STAC (Sentinel-1) | No (search) | ✅ Ready |
| JRC Global Surface Water | No | ✅ Ready |
| Open Development Cambodia | No | ✅ Ready |
| MRC Data Services | Yes (PDIES) | ⚠️ Placeholder |
| NASA FIRMS | Free key | 🔧 Optional |

## 🤖 AI Risk Assessment

Multi-factor risk engine: Rainfall (25%) + Hydrology (30%) + Soil (15%) + Seasonal (15%) + Historical (15%)

Risk Categories: 🟢 Low (0-25%) | 🟡 Moderate (25-50%) | 🟠 High (50-75%) | 🔴 Very High (75-100%)

## 📄 License

Built for the Build With Open Data hackathon.

## 🙏 Attribution

Open-Meteo (CC-BY 4.0) | Copernicus | EC JRC/Google | Open Development Cambodia | MRC | geoBoundaries (CC-BY 4.0)
