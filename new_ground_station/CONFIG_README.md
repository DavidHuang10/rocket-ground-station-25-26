# Dynamic Telemetry Dashboard Configuration

## Overview

The ground station now uses a configuration-driven approach! All dashboard panels, their types, and display settings are defined in `public/config.json`.

## Benefits

✅ Add new telemetry fields without touching frontend code
✅ Reorganize dashboard by editing JSON
✅ Change display names, units, and precision dynamically
✅ No frontend rebuild needed for config changes

## How It Works

### 1. Configuration File: `public/config.json`

Defines all panels and their metadata:
- **Panel types**: `mission_timer`, `indicator`, `chart`, `multi_chart`, `float`, `grouped`, `boolean_grid`
- **Field metadata**: name, unit, precision, description

### 2. Frontend Automatically:
- Fetches config on page load
- Builds telemetry data structure dynamically
- Renders panels using Vue `v-for`
- Initializes charts based on config

### 3. Backend:
- Serves `config.json` as static file
- Data format remains unchanged (`format_for_frontend()` in `utils.py`)

## Panel Types

### `mission_timer`
Displays mission elapsed time in HH:MM:SS format.

```json
{
  "id": "mission_time",
  "type": "mission_timer",
  "title": "Mission Time",
  "order": 1
}
```

### `indicator`
Large value with label mapping (e.g., flight stage 2 → "Boost").

```json
{
  "id": "flight_stage",
  "type": "indicator",
  "title": "Flight Stage",
  "fields": ["stage"],
  "order": 2,
  "mapping": ["Standby", "Armed", "Boost", "Coast", "Drogue", "Main", "Landed"]
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
  "order": 3,
  "chart_color": "#4caf50"
}
```

### `multi_chart`
Multiple series on one chart (e.g., X/Y/Z axes).

```json
{
  "id": "acceleration",
  "type": "multi_chart",
  "title": "Acceleration",
  "fields": ["accelx", "accely", "accelz"],
  "unit": "m/s²",
  "order": 7,
  "labels": ["X", "Y", "Z"],
  "colors": ["#f44336", "#4caf50", "#2196f3"]
}
```

### `float`
Single numeric value with unit.

```json
{
  "id": "battery_voltage",
  "type": "float",
  "title": "Battery Voltage",
  "fields": ["battery_voltage"],
  "unit": "V",
  "precision": 2,
  "order": 5
}
```

### `grouped`
Multiple related values displayed together.

```json
{
  "id": "gps",
  "type": "grouped",
  "title": "GPS Position",
  "order": 6,
  "items": [
    {"label": "Lat", "field": "lat", "unit": "°", "precision": 7},
    {"label": "Lng", "field": "long", "unit": "°", "precision": 7},
    {"label": "Alt", "field": "gps_alt", "unit": "m", "precision": 1}
  ]
}
```

### `boolean_grid`
Grid of status indicators (good/bad).

```json
{
  "id": "pyro_continuity",
  "type": "boolean_grid",
  "title": "Pyro Continuity",
  "order": 11,
  "items": [
    {"label": "Drogue 1", "field": "drogue_cont_1"},
    {"label": "Drogue 2", "field": "drogue_cont_2"},
    {"label": "Main 1", "field": "main_cont_1"},
    {"label": "Main 2", "field": "main_cont_2"}
  ]
}
```

## Adding a New Telemetry Field

### Example: Adding Engine Temperature

**Step 1: Update `models.py`** (if it's a new CSV field)
```python
engine_temp: float = Field(..., description="Engine temperature (°C)")
```

**Step 2: Update `utils.py` `format_for_frontend()`**
```python
{"time": time, "source": "engine_temp", "value": telemetry.engine_temp},
```

**Step 3: Add to `public/config.json`**

Add field metadata:
```json
"engine_temp": {
  "name": "Engine Temperature",
  "unit": "°C",
  "precision": 1,
  "description": "Engine combustion chamber temperature"
}
```

Add a panel:
```json
{
  "id": "engine_temp",
  "type": "float",
  "title": "Engine Temperature",
  "fields": ["engine_temp"],
  "unit": "°C",
  "precision": 1,
  "order": 12
}
```

**Done!** Refresh the browser and the new panel appears automatically.

## Reorganizing the Dashboard

Simply change the `order` field in any panel:

```json
{"id": "battery_voltage", "order": 1}  // Move to top
{"id": "altitude", "order": 2}         // Second position
```

## Changing Display Settings

Edit any panel's properties:

```json
{
  "id": "altitude",
  "precision": 2,              // Change from 1 to 2 decimal places
  "chart_color": "#ff0000"    // Change chart color
}
```

Save `config.json`, hard refresh browser (Ctrl+Shift+R), done!

## File Structure

```
new_ground_station/
├── config.py              # Config loader and validation
├── models.py              # Telemetry data model
├── utils.py               # format_for_frontend() helper
├── main.py                # FastAPI server
└── public/
    ├── config.json        # ← Dashboard configuration
    ├── index.html         # Dynamic Vue template
    ├── main.js            # Config-driven Vue app
    └── style.css          # Styling
```

## Testing

```bash
# Start server
uvicorn main:app --reload --port 8000

# Open browser
open http://localhost:8000

# Check browser console for config loading
# Should see: "Configuration loaded: {panels: [...], field_metadata: {...}}"
```

## Troubleshooting

**Panel doesn't appear:**
- Check `order` field is unique
- Verify `fields` array contains valid telemetry sources
- Check browser console for errors

**Chart not rendering:**
- Ensure canvas ID matches: `chart-${panel.id}`
- Check `type` is `chart` or `multi_chart`
- Verify `fields` array is populated

**Values show as 0:**
- Check field name matches `utils.py` format_for_frontend() source names
- Verify telemetry is flowing (WebSocket connected)

## Advanced: Custom Panel Types

To add a new panel type (e.g., `3d_model`):

1. Add rendering logic to `index.html`:
```html
<div v-else-if="panel.type === '3d_model'" class="panel">
  <h2>{{ panel.title }}</h2>
  <!-- Your custom rendering here -->
</div>
```

2. Add initialization logic to `main.js` if needed:
```javascript
if (panel.type === '3d_model') {
  this.init3DModel(panel);
}
```

3. Define in config:
```json
{"id": "rocket_3d", "type": "3d_model", "title": "Rocket Orientation"}
```
