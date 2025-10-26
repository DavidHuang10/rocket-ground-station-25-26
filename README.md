# ERIS Ground Station

Real-time telemetry dashboard for ERIS Gamma rocket flight computer. Receives 29-field CSV telemetry via WebSocket at 2Hz.

## Architecture

**Backend (FastAPI)**
- [main.py](new_ground_station/main.py) - WebSocket server, client management, telemetry broadcasting
- [models.py](new_ground_station/models.py) - CSV parsing and data validation (Pydantic)
- [utils.py](new_ground_station/utils.py) - Frontend data formatting, mock telemetry generator
- [config.py](new_ground_station/config.py) - Unused legacy config (frontend handles configuration)

**Frontend (Vanilla JS)**
- [index.html](new_ground_station/public/index.html) - Dashboard UI structure
- [main.js](new_ground_station/public/main.js) - WebSocket client, dynamic panel rendering
- [config.json](new_ground_station/public/config.json) - Panel definitions and field metadata
- [style.css](new_ground_station/public/style.css) - Dashboard styling

## Data Flow

1. Telemetry → Queue (`telemetry_queue`)
2. Queue → Parser (`TelemetryData.from_csv()`)
3. Parser → Formatter (`format_for_frontend()`)
4. Formatter → WebSocket broadcast (all connected clients)
5. Frontend → Dynamic panels (based on `config.json`)

## Key Features

- **Config-driven UI**: Add/remove dashboard panels by editing [config.json](new_ground_station/public/config.json)
- **Panel types**: `indicator` (status), `chart` (time-series), `boolean_grid` (continuity checks)
- **Real-time updates**: 500ms telemetry interval, live chart updates
- **Health monitoring**: `/health` endpoint reports client count and queue size

## Adding Telemetry Fields

See [CONFIGURATION.md](new_ground_station/CONFIGURATION.md) for detailed steps on adding new fields to the dashboard.

## API Endpoints

- `GET /health` - Health check with client/queue stats
- `POST /telemetry/inject` - Manual CSV injection for testing
- `WS /ws` - WebSocket telemetry stream