# Storage System Update - Design Document

## Goals
1. **Never destructive** - All data always backed up
2. **Clear charts non-destructively** - Remove pre-flight idle data, keep only flight data
3. **Organized flights** - Each flight has its own file
4. **Late-joining clients** - Get full flight history (excluding pre-flight idle)
5. **Detailed analysis** - Backend endpoint for field-specific data (for zooming)

## Core Concept

### Time Zero Adjustment
- Backend receives telemetry with `cur_time` = seconds since rocket boot
- On "Clear Charts" (takeoff), backend records `takeoff_offset_time`
- All subsequent data is adjusted: `flight_time = cur_time - takeoff_offset_time`
- Charts show T+0 = takeoff, not boot time

### Storage Structure
```
new_ground_station/
├── flight_logs/
│   ├── current.csv              # Active flight data (always present)
│   ├── flight_2024-11-05_14-23-15.csv  # Saved flights (renamed from current.csv)
│   └── flight_2024-11-05_16-45-32.csv
└── backups/
    ├── pre_flight_2024-11-05_14-23-15.csv  # Pre-takeoff data (from clear)
    ├── pre_flight_2024-11-05_16-45-32.csv
    └── flight_2024-11-05_14-23-15.csv      # Copy of saved flights
```

## File Lifecycle

### On Server Start
1. Create empty `flight_logs/current.csv` with headers
2. Initialize `takeoff_offset_time = None` (not yet taken off)
3. Append all incoming telemetry to `current.csv`

### On "Clear Charts" (Takeoff Button)
1. Record current `cur_time` from last telemetry packet as `takeoff_offset_time`
2. Generate timestamp for save: `timestamp = current_wall_clock_time` (ISO format: `2024-11-05_14-23-15`)
3. Move `current.csv` → `backups/pre_flight_{timestamp}.csv` (ONLY to backups, NOT flight_logs)
4. Create new empty `flight_logs/current.csv` with headers
5. Broadcast clear event to all connected clients via WebSocket:
   ```json
   {
     "type": "clear",
     "takeoff_offset": 135.5,
     "takeoff_time": "2024-11-05T14:23:15Z"
   }
   ```
6. Clients clear their `telemetryData` arrays and reset charts

### On "Save Flight"
1. Generate timestamp: `timestamp = current_wall_clock_time` (time of save action)
2. Copy `current.csv` → `backups/flight_{timestamp}.csv` (backup copy)
3. Copy `current.csv` → `flight_logs/flight_{timestamp}.csv` (official save)
4. Keep `current.csv` active (continues recording)

### On "Save and Clear"
1. Generate timestamp: `timestamp = current_wall_clock_time` (time of save action)
2. Copy `current.csv` → `backups/flight_{timestamp}.csv` (backup copy)
3. Move `current.csv` → `flight_logs/flight_{timestamp}.csv` (official save)
4. Create new empty `current.csv`
5. Reset `takeoff_offset_time = None`
6. Broadcast clear event to all connected clients via WebSocket:
   ```json
   {
     "type": "clear",
     "takeoff_offset": null,
     "takeoff_time": null
   }
   ```
7. Clients clear their `telemetryData` arrays and reset charts

## Backend Endpoints

### `GET /telemetry/current`
Returns all data from `current.csv` with adjusted times.
```json
{
  "session": {
    "start_time": "2024-11-05T14:23:15Z",
    "takeoff_time": "2024-11-05T14:25:30Z",  # null if not taken off yet
    "packet_count": 1234,
    "takeoff_offset": 135.5  # seconds, null if not taken off
  },
  "data": [
    {"time": 0.0, "source": "altitude", "value": 0.0},
    {"time": 0.5, "source": "altitude", "value": 1.2},
    ...
  ]
}
```

**Time adjustment**: If `takeoff_offset` exists, all times are `cur_time - takeoff_offset`.

### `GET /telemetry/field/{field_name}`
Returns all data for a specific field (for zoom/detailed analysis).
```json
{
  "field": "altitude",
  "unit": "m AGL",
  "data": [
    {"time": 0.0, "value": 0.0},
    {"time": 0.5, "value": 1.2},
    ...
  ]
}
```

### `POST /telemetry/clear` (Takeoff)
1. Move `current.csv` → `backups/pre_flight_{timestamp}.csv` (ONLY to backups)
2. Record `takeoff_offset_time = current_time_from_last_telemetry_packet`
3. Create new `current.csv`
4. Broadcast to all WebSocket clients:
   ```json
   {
     "type": "clear",
     "takeoff_offset": 135.5,
     "takeoff_time": "2024-11-05T14:23:15Z"
   }
   ```

HTTP Response:
```json
{
  "status": "success",
  "backup_filename": "pre_flight_2024-11-05_14-23-15.csv",
  "takeoff_offset": 135.5,
  "takeoff_time": "2024-11-05T14:23:15Z"
}
```

### `POST /telemetry/save`
1. Generate timestamp (time of save action)
2. Copy `current.csv` → `backups/flight_{timestamp}.csv`
3. Copy `current.csv` → `flight_logs/flight_{timestamp}.csv`
4. Keep `current.csv` active (continues recording)

HTTP Response:
```json
{
  "status": "success",
  "filename": "flight_2024-11-05_14-28-45.csv",
  "saved_at": "2024-11-05T14:28:45Z"
}
```

### `POST /telemetry/save-and-clear`
1. Generate timestamp (time of save action)
2. Copy `current.csv` → `backups/flight_{timestamp}.csv`
3. Move `current.csv` → `flight_logs/flight_{timestamp}.csv`
4. Create new empty `current.csv`
5. Reset `takeoff_offset_time = None`
6. Broadcast to all WebSocket clients:
   ```json
   {
     "type": "clear",
     "takeoff_offset": null,
     "takeoff_time": null
   }
   ```

HTTP Response:
```json
{
  "status": "success",
  "filename": "flight_2024-11-05_14-28-45.csv",
  "saved_at": "2024-11-05T14:28:45Z"
}
```

## Frontend Changes

### New "Takeoff" Button
- Label: "Clear Charts (Takeoff)"
- Calls `/telemetry/clear`
- Confirmation: "Clear charts and mark takeoff? Pre-flight data will be backed up."

### WebSocket Clear Signal Handler
When receiving clear event from backend:
```javascript
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);

  // Handle clear signal
  if (data.type === 'clear') {
    // Clear all chart data
    for (const key in this.telemetryData) {
      this.telemetryData[key] = [];
    }
    this.updateCharts();

    // Store takeoff info (if provided)
    if (data.takeoff_offset !== null) {
      console.log(`🚀 Takeoff! T+0 = ${data.takeoff_time}`);
      // Optional: Display takeoff time in UI
    } else {
      console.log('📊 Charts cleared for new session');
    }
    return;
  }

  // Handle regular telemetry (already time-adjusted by backend)
  const telemetryArray = data;
  this.processTelemetry(telemetryArray);
}
```

### Load Current Session
On page load, fetch `/telemetry/current`:
- If `takeoff_offset` exists, charts start at T+0 (flight time)
- If `takeoff_offset` is null, charts show boot time (pre-flight)

## Data Flow Example

### Scenario: Full Flight Session

**T-135s (rocket on pad, powered on)**
- Backend: `current.csv` accumulating data, `takeoff_offset = None`
- Client 1: Connected, sees idle data on charts (altitude ~0, stage=0)

**T-0s (operator presses "Takeoff" button)**
- Backend: Moves `current.csv` → `backups/pre_flight_14-23-15.csv`, creates new `current.csv`, sets `takeoff_offset = 135.5`
- Client 1: Receives clear signal, resets charts to empty
- All new data is now relative to T+0

**T+45s (apogee, Client 2 joins late)**
- Client 2: Opens dashboard, calls `/telemetry/current`
- Backend: Returns 45 seconds of flight data (adjusted times: 0.0 → 45.0)
- Client 2: Populates charts, sees full flight from T+0
- Client 2: Connects WebSocket, receives live updates

**T+180s (landed, operator presses "Save Flight")**
- Backend: Copies `current.csv` → `backups/flight_14-23-15.csv` + `flight_logs/flight_14-23-15.csv`
- `current.csv` stays active for potential second flight

**T+300s (operator presses "Save and Clear" for next flight)**
- Backend: Saves current flight, resets everything
- Both clients: Charts clear, ready for next flight

## Advantages

### Simplicity
- Single `current.csv` is always the source of truth
- Clear file lifecycle: active → backup → official save
- No complex state management, just file operations + offset variable

### Elegance
- Time offset handled transparently by backend
- Clients don't need to know about boot time vs flight time
- All timestamps in client are flight-relative (T+0 = takeoff)

### Functionality
- ✅ Never destructive (all data backed up)
- ✅ Clear charts removes idle data
- ✅ Each flight gets own file
- ✅ Late joiners get full flight history
- ✅ Field-specific endpoint for zoom
- ✅ Multiple flights per session supported

### Robustness
- If server crashes, `current.csv` persists on disk
- On restart, can resume from `current.csv` or start fresh
- Backups folder is append-only (never deleted)

## Edge Cases

### Multiple Takeoffs Without Save
- First takeoff: `pre_flight_14-23-15.csv`
- Second takeoff: `pre_flight_14-23-16.csv` (new timestamp)
- Each clear generates unique backup file

### Server Restart Mid-Flight
- Option 1: Keep `current.csv`, reset `takeoff_offset = None` (client charts show full data including pre-flight)
- Option 2: Prompt operator: "Resume flight or start new session?"

### Client Connects Before Takeoff
- Charts show boot-relative time
- After takeoff + clear, charts reset to T+0
- Client sees seamless transition

## Implementation Plan

### Phase 1: Storage Infrastructure (Backend)
**Goal**: Set up folder structure, file operations, tracking variables

**Tasks**:
1. Create `flight_logs/` and `backups/` directories on server start
2. Add state variables to backend:
   - `takeoff_offset_time: Optional[float] = None`
   - `session_start_time: datetime` (wall clock)
   - `last_telemetry_time: float` (from CSV)
3. Modify telemetry ingestion to track `last_telemetry_time`
4. Implement file utility functions:
   - `generate_timestamp() -> str` (returns `2024-11-05_14-23-15`)
   - `move_file(src, dest)`
   - `copy_file(src, dest)`
5. Update `current.csv` to always write to `flight_logs/current.csv`

**Files to modify**:
- `storage.py` or `main.py` (wherever CSV writing happens)

**Testing**:
- Server creates folders on start
- Telemetry writes to `flight_logs/current.csv`
- Variables update correctly

---

### Phase 2: Clear/Save Endpoints (Backend)
**Goal**: Implement the three save operations with proper file handling

**Tasks**:
1. Update `POST /telemetry/clear`:
   - Move `current.csv` → `backups/pre_flight_{timestamp}.csv`
   - Set `takeoff_offset_time = last_telemetry_time`
   - Create new empty `current.csv`
   - Return JSON response with offset + timestamp

2. Update `POST /telemetry/save`:
   - Copy `current.csv` → `backups/flight_{timestamp}.csv`
   - Copy `current.csv` → `flight_logs/flight_{timestamp}.csv`
   - Return JSON response with filename

3. Update `POST /telemetry/save-and-clear`:
   - Copy to backups, move to flight_logs
   - Reset `takeoff_offset_time = None`
   - Create new `current.csv`
   - Return JSON response

**Files to modify**:
- `main.py` (endpoints)
- `storage.py` (helper functions)

**Testing**:
- Clear creates `pre_flight_*.csv` in backups only
- Save creates `flight_*.csv` in both folders
- Save-and-clear creates flight file and resets state

---

### Phase 3: Time Adjustment (Backend)
**Goal**: Apply takeoff offset to all outgoing telemetry

**Tasks**:
1. Update `format_for_frontend()` in `utils.py`:
   - Accept `takeoff_offset` parameter
   - If offset exists: `adjusted_time = raw_time - takeoff_offset`
   - Return adjusted times in JSON

2. Update `GET /telemetry/current`:
   - Load all data from `current.csv`
   - Apply time adjustment if `takeoff_offset_time` exists
   - Return session metadata (offset, takeoff_time, etc.)

3. Update WebSocket broadcast:
   - Apply time adjustment to live telemetry before sending
   - Ensure consistent time format across all messages

**Files to modify**:
- `utils.py` (time adjustment logic)
- `main.py` (endpoints and WebSocket)

**Testing**:
- Before takeoff: times are raw boot times (135.5, 136.0, ...)
- After clear: times reset to 0.0, 0.5, 1.0, ...
- Late-joining clients receive adjusted times

---

### Phase 4: WebSocket Clear Broadcast (Backend)
**Goal**: Notify all connected clients when charts should clear

**Tasks**:
1. Create broadcast helper function:
   ```python
   async def broadcast_clear(takeoff_offset: Optional[float], takeoff_time: Optional[str]):
       message = {
           "type": "clear",
           "takeoff_offset": takeoff_offset,
           "takeoff_time": takeoff_time
       }
       await manager.broadcast(json.dumps(message))
   ```

2. Call `broadcast_clear()` in:
   - `POST /telemetry/clear` (with offset + time)
   - `POST /telemetry/save-and-clear` (with null values)

3. Update WebSocket message types:
   - Regular telemetry: JSON array `[{time, source, value}, ...]`
   - Clear signal: JSON object `{"type": "clear", ...}`
   - Pong: String `"pong"`

**Files to modify**:
- `main.py` (WebSocket manager, endpoints)

**Testing**:
- Clear button sends clear signal to all clients
- Clients receive message and can parse it
- Multiple clients all clear simultaneously

---

### Phase 5: Frontend Clear Handler (Frontend)
**Goal**: Handle clear signals and reset charts

**Tasks**:
1. Update `ws.onmessage` in `main.js`:
   - Detect `data.type === 'clear'`
   - Clear all `telemetryData` arrays
   - Call `updateCharts()` to redraw empty charts
   - Log takeoff info if provided

2. Add confirmation dialog to `clearCharts()` method:
   - Update button label: "Clear Charts (Takeoff)"
   - Confirm: "Mark takeoff and clear charts? Pre-flight data will be backed up."

3. Update `loadCurrentSession()`:
   - Check `session.takeoff_offset` from backend response
   - Initialize charts with time-adjusted data
   - Display session info if available

**Files to modify**:
- `main.js` (WebSocket handler, clear method, session loader)
- `index.html` (button label)

**Testing**:
- Click clear → confirmation appears
- After confirm → all clients clear charts
- Late joiners load only post-takeoff data
- Charts show T+0, T+1, etc. (not boot time)

---

### Phase 6: Field Endpoint (Backend - Optional)
**Goal**: Enable zoom functionality by fetching single-field data

**Tasks**:
1. Create `GET /telemetry/field/{field_name}`:
   - Read `current.csv` (or use in-memory cache)
   - Filter for specific field
   - Apply time adjustment
   - Return JSON array

2. Add field metadata from config:
   - Unit, precision, description
   - Return in response for frontend use

**Files to modify**:
- `main.py` (new endpoint)
- `models.py` or `utils.py` (CSV parsing)

**Testing**:
- Fetch `/telemetry/field/altitude`
- Returns all altitude data with adjusted times
- Frontend can use for detailed zoom charts

---

### Phase 7: UI Polish (Frontend - Optional)
**Goal**: Improve user experience with better feedback

**Tasks**:
1. Add session info display:
   - Takeoff time (if set)
   - Session duration
   - Total packets received

2. Add save confirmation messages:
   - "Flight saved as flight_2024-11-05_14-28-45.csv"
   - Show in alert or toast notification

3. Update button states:
   - Disable "Clear" if already cleared
   - Show loading state during save operations

**Files to modify**:
- `index.html` (UI elements)
- `main.js` (state management, notifications)
- `style.css` (button states, info panel)

**Testing**:
- Session info displays correctly
- Save confirmations appear
- Buttons behave correctly

---

## Implementation Order Summary

**Must have (MVP)**:
1. Phase 1: Storage Infrastructure
2. Phase 2: Clear/Save Endpoints
3. Phase 3: Time Adjustment
4. Phase 4: WebSocket Clear Broadcast
5. Phase 5: Frontend Clear Handler

**Nice to have**:
6. Phase 6: Field Endpoint (for zoom)
7. Phase 7: UI Polish

**Estimated effort**:
- MVP (Phases 1-5): ~4-6 hours
- Full system (Phases 1-7): ~6-8 hours

---

## Key Technical Decisions

### Why move vs copy for clear?
- **Clear**: MOVE to backups (pre-flight data no longer needed in active session)
- **Save**: COPY (flight data stays active for potential continued recording)

### Why adjust time in backend?
- **Simplicity**: Frontend doesn't need offset logic
- **Consistency**: All clients receive same adjusted times
- **Late joiners**: Automatically get correct times from `/telemetry/current`

### Why broadcast clear signal?
- **Synchronization**: All clients clear at exactly the same moment
- **Reliability**: Works even if client loses HTTP connection
- **Real-time**: Operator sees immediate feedback

### Why store takeoff_offset as variable, not in file?
- **Performance**: No disk I/O on every telemetry packet
- **Simplicity**: One variable vs. parsing metadata from CSV
- **Reset-friendly**: Easy to reset to `None` for new session
