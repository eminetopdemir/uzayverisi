# Space Weather Communication DSS

Real-time **Deep-Space / Satellite Communication Decision Support System** that monitors space weather conditions and provides adaptive link-budget analysis with ML-powered predictions.

## Features

- **Live Link-Budget Analysis** — SNR, data loss, received power calculations based on real space weather data
- **Adaptive Decision Engine** — Automatic modulation, coding rate, and power recommendations
- **ML Predictions** — Random Forest model trained on space weather parameters
- **Real-Time Alerts** — WebSocket-based instant alert system across devices
- **Interactive Dashboard** — React frontend with scenario simulation and optimization panels

## Architecture

| Layer | Tech |
|-------|------|
| Backend | FastAPI + Uvicorn (Python 3.12) |
| Frontend | React + Vite + Tailwind CSS |
| Real-time | WebSocket |
| Deployment | Docker Compose + Nginx reverse proxy |

## Quick Start

### Docker (recommended)

```bash
docker compose up -d --build
```

The app will be available at `http://localhost`.

### Local Development

```bash
# Backend
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000

# Frontend
cd frontend
npm install
npm run dev
```

## Data Sources

- **GOES satellite** — Solar X-ray flux, proton flux
- **OMNIWeb** — Solar wind speed, IMF Bz, proton density
- **RTSW** — Real-time solar wind plot data

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/scenarios` | List all space weather scenarios |
| POST | `/api/predict` | ML prediction for given parameters |
| GET | `/api/alert-status` | Current alert state |
| WS | `/ws/alerts` | Real-time alert stream |


## License 

MIT

