# Dashboard Configuration

## Why config.json?

Defines what telemetry fields are displayed and how. Change the dashboard layout without modifying code—just edit JSON and refresh the browser.

## Adding a New Telemetry Field

Example: Adding `engine_temp` to the broadcast and dashboard.

### 1. Update CSV parsing in [models.py](models.py)
Add the field to `TelemetryData`:
```python
engine_temp: float = Field(..., description="Engine temperature (°C)")
```

Update `from_csv()` to parse it from the CSV string (adjust field index):
```python
engine_temp=float(fields[29]),
```

### 2. Add to backend broadcast in [utils.py](utils.py)
Add to the list in `format_for_frontend()`:
```python
{"time": time, "source": "engine_temp", "value": telemetry.engine_temp},
```

### 3. Add to frontend config in [public/config.json](public/config.json)
Add field metadata:
```json
"engine_temp": {
  "name": "Engine Temperature",
  "unit": "°C",
  "precision": 1,
  "description": "Engine combustion chamber temperature"
}
```

Add a panel to display it:
```json
{
  "id": "engine_temp",
  "type": "chart",
  "title": "Engine Temperature",
  "fields": ["engine_temp"],
  "unit": "°C",
  "precision": 1,
  "order": 18,
  "chart_color": "#ff5722"
}
```

### 4. Done
Refresh browser—new panel appears automatically.

## Panel Types Reference

### `timer`
Displays formatted time from milliseconds (converts to MM:SS or HH:MM:SS format).
```json
{
  "id": "mission_timer",
  "type": "timer",
  "title": "Mission Elapsed Time",
  "fields": ["cur_time"],
  "order": 1
}
```

### `indicator`
Large numeric value with optional text mapping (e.g., `0 → "Idle"`).
```json
{
  "id": "flight_stage",
  "type": "indicator",
  "title": "Flight Stage",
  "fields": ["stage"],
  "order": 2,
  "mapping": ["Idle", "Takeoff", "Burn", "Coast", "Apogee", "Main Parachute", "Landed"]
}
```

For numeric indicators without mapping:
```json
{
  "id": "flight_index",
  "type": "indicator",
  "title": "Flight Index",
  "fields": ["flight_index"],
  "precision": 0,
  "order": 22
}
```

### `chart`
Single time-series line chart.
```json
{
  "id": "altitude",
  "type": "chart",
  "title": "Altitude",
  "fields": ["altitude"],
  "unit": "m AGL",
  "precision": 1,
  "order": 2,
  "chart_color": "#4caf50"
}
```

### `boolean_grid`
Grid of good/bad status indicators.
```json
{
  "id": "pyro_continuity",
  "type": "boolean_grid",
  "title": "Pyro Continuity",
  "order": 18,
  "items": [
    {"label": "Drogue 1", "field": "drogue_cont_1"},
    {"label": "Drogue 2", "field": "drogue_cont_2"}
  ]
}
```

## File Structure

```
models.py           # CSV → Python objects (TelemetryData)
utils.py            # Python → JSON for frontend (format_for_frontend)
public/config.json  # Defines what frontend displays
public/main.js      # Reads config, builds UI dynamically
```

## How It Works

1. **Backend**: Sends all telemetry fields as JSON via WebSocket
2. **Frontend**: Fetches `config.json` on load
3. **Frontend**: Builds dashboard panels dynamically based on config
4. **Frontend**: Updates charts/values as telemetry arrives

**Note**: `config.py` exists but is unused. Backend always sends all fields. Frontend uses config to decide what to display.
