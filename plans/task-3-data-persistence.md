# Task 3: Data Persistence Strategy

**Priority:** 1 (Must be completed first)
**Status:** Planning
**Dependencies:** None

---

## Overview

Implement a data persistence solution to store telemetry data beyond the current 100-point in-memory limit, enabling data to survive page refreshes and creating permanent flight records for post-flight analysis.

---

## Problem Statement

**Current limitations:**
- Only 100 data points stored in memory (lines 167-169 in main.js)
- Data lost on page refresh/browser crash
- No permanent flight records
- Can't review historical flights
- Typical 10-minute flight at 2Hz = 1,200 packets, but only last 100 visible

**Requirements:**
- Store all telemetry data during flight (unlimited or high limit like 10,000 points)
- Survive page refreshes
- Create permanent records for analysis
- Run on Raspberry Pi (SD card storage)
- Support manual reset for new flights

---

## Storage Options Analysis

### Option A: Server-Side File Logging (RECOMMENDED)

**How it works:**
1. Backend saves each telemetry packet to disk in real-time
2. Maintains in-memory buffer of current flight session
3. On page refresh, frontend fetches current session data from backend
4. Files stored on Raspberry Pi SD card

**File Structure:**
```
new_ground_station/
├── flight_logs/
│   ├── flight_2025-11-02_14-30-00.csv    # Raw CSV telemetry
│   ├── flight_2025-11-02_14-30-00.json   # Processed JSON for reload
│   ├── flight_2025-11-02_15-45-30.csv
│   ├── flight_2025-11-02_15-45-30.json
│   └── ...
```

**Pros:**
- ✅ Data survives page refreshes, browser crashes, server restarts
- ✅ Creates permanent flight records for analysis
- ✅ Works across multiple connected devices (all see same data)
- ✅ Can export/analyze data in Python/MATLAB/Excel later
- ✅ Raspberry Pi SD card has plenty of space
- ✅ Industry standard approach for telemetry systems

**Cons:**
- ❌ Need to implement backend storage logic
- ❌ SD card writes (minimal at 2Hz, ~120KB/min)
- ❌ Need to manage disk space (auto-delete old flights)

**Storage Requirements:**
- 29 CSV fields @ 2Hz = ~60 bytes/packet
- 10-minute flight = 1,200 packets = ~72KB raw CSV
- With JSON metadata: ~200KB per flight
- 32GB SD card = 160,000 flights capacity

---

### Option B: Browser LocalStorage

**How it works:**
- Store telemetry data in browser's localStorage API
- Persists across page refreshes
- No backend changes needed

**Pros:**
- ✅ Simple to implement (JSON.stringify/parse)
- ✅ No SD card writes
- ✅ Fast access

**Cons:**
- ❌ Data only exists in that specific browser on that device
- ❌ Clear browser cache = data lost
- ❌ Can't view data from another device
- ❌ 5-10MB limit (~50,000 data points max)
- ❌ No permanent record for analysis
- ❌ Not suitable for mission-critical data

---

### Option C: In-Memory Only

**How it works:**
- Remove 100-point limit, store everything in JavaScript memory
- Data lost on page refresh

**Pros:**
- ✅ Zero implementation complexity
- ✅ Fastest access

**Cons:**
- ❌ No persistence
- ❌ Lost on refresh/crash
- ❌ Not suitable for real flights

---

## Recommended Solution: Option A (Server-Side Logging)

For a rocket ground station at real launches, you need reliability and permanent records.

---

## Implementation Plan

### Phase 1: Backend Storage Module

**New file: `storage.py`**

```python
"""
Telemetry data storage and session management.
Handles writing telemetry to disk and managing flight sessions.
"""

import json
import csv
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional
from models import TelemetryData

class FlightSession:
    """Manages a single flight session with logging."""

    def __init__(self, session_id: str, log_dir: Path):
        self.session_id = session_id
        self.start_time = datetime.now()
        self.log_dir = log_dir
        self.telemetry_buffer: List[TelemetryData] = []

        # Create log files
        self.csv_path = log_dir / f"flight_{session_id}.csv"
        self.json_path = log_dir / f"flight_{session_id}.json"

        # Initialize CSV file with headers
        self._init_csv_file()

    def add_telemetry(self, telemetry: TelemetryData):
        """Add telemetry packet to session."""
        self.telemetry_buffer.append(telemetry)
        self._write_csv(telemetry)
        self._write_json_checkpoint()

    def get_all_data(self) -> List[Dict]:
        """Return all telemetry data as formatted dicts."""
        from utils import format_for_frontend
        result = []
        for telem in self.telemetry_buffer:
            result.extend(format_for_frontend(telem))
        return result

    def _init_csv_file(self):
        """Create CSV file with headers."""
        # Implementation details...

    def _write_csv(self, telemetry: TelemetryData):
        """Append telemetry to CSV file."""
        # Implementation details...

    def _write_json_checkpoint(self):
        """Write JSON checkpoint for fast reload."""
        # Implementation details...


class StorageManager:
    """Manages flight sessions and log directory."""

    def __init__(self, log_dir: str = "flight_logs"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        self.current_session: Optional[FlightSession] = None
        self._start_new_session()

    def _start_new_session(self):
        """Start a new flight session."""
        session_id = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self.current_session = FlightSession(session_id, self.log_dir)

    def add_telemetry(self, telemetry: TelemetryData):
        """Add telemetry to current session."""
        if self.current_session:
            self.current_session.add_telemetry(telemetry)

    def reset_session(self):
        """Start new flight session (reset)."""
        self._start_new_session()

    def get_current_data(self) -> List[Dict]:
        """Get all data from current session."""
        if self.current_session:
            return self.current_session.get_all_data()
        return []

    def get_session_info(self) -> Dict:
        """Get current session metadata."""
        if self.current_session:
            return {
                "session_id": self.current_session.session_id,
                "start_time": self.current_session.start_time.isoformat(),
                "packet_count": len(self.current_session.telemetry_buffer)
            }
        return {}
```

### Phase 2: Backend API Changes

**Modify `main.py`:**

1. **Initialize storage manager:**
```python
from storage import StorageManager

storage_manager = StorageManager(log_dir="flight_logs")
```

2. **Save telemetry in broadcast loop:**
```python
async def broadcast_telemetry():
    while True:
        csv_data = await telemetry_queue.get()

        try:
            telemetry = TelemetryData.from_csv(csv_data)

            # SAVE TO STORAGE
            storage_manager.add_telemetry(telemetry)

            # Continue with broadcast...
            message_data = format_for_frontend(telemetry)
            # ... rest of broadcast logic
```

3. **Add new API endpoints:**
```python
@app.get("/telemetry/current")
async def get_current_telemetry():
    """Get all telemetry from current flight session."""
    return {
        "data": storage_manager.get_current_data(),
        "session": storage_manager.get_session_info()
    }

@app.post("/telemetry/reset")
async def reset_telemetry():
    """Start a new flight session (clears current data)."""
    storage_manager.reset_session()
    return {
        "status": "success",
        "message": "New flight session started",
        "session": storage_manager.get_session_info()
    }

@app.get("/telemetry/sessions")
async def list_sessions():
    """List all past flight sessions (optional - future feature)."""
    # Implementation to list files in flight_logs/
    pass
```

### Phase 3: Frontend Changes

**Modify `main.js`:**

1. **Remove data limit:**
```javascript
data() {
    return {
        // ... existing fields
        maxDataPoints: null,  // Remove limit (was 100)
        sessionId: null,
        isLoadingHistory: false
    };
}
```

2. **Load data on mount:**
```javascript
async mounted() {
    await this.loadConfig();
    await this.loadCurrentSession();  // NEW: Load existing data
    this.initTelemetryData();
    await this.$nextTick();
    this.initCharts();
    this.connect();
}
```

3. **Add data loading method:**
```javascript
methods: {
    async loadCurrentSession() {
        try {
            this.isLoadingHistory = true;
            const response = await fetch(`http://localhost:${this.port}/telemetry/current`);
            const result = await response.json();

            // Populate telemetry data from history
            result.data.forEach(item => {
                const { time, source, value } = item;
                if (this.telemetryData.hasOwnProperty(source)) {
                    this.telemetryData[source].push({ time, value });
                }
            });

            this.sessionId = result.session.session_id;
            console.log(`Loaded ${result.data.length} data points from session ${this.sessionId}`);

        } catch (e) {
            console.error('Failed to load session history:', e);
        } finally {
            this.isLoadingHistory = false;
        }
    },

    async resetCharts() {
        if (!confirm('Start new flight session? This will clear all current data.')) {
            return;
        }

        try {
            // Call backend reset
            const response = await fetch(`http://localhost:${this.port}/telemetry/reset`, {
                method: 'POST'
            });
            const result = await response.json();

            // Clear frontend data
            for (const key in this.telemetryData) {
                this.telemetryData[key] = [];
            }

            // Update charts
            this.updateCharts();

            this.sessionId = result.session.session_id;
            console.log('New flight session started:', this.sessionId);

        } catch (e) {
            console.error('Failed to reset session:', e);
        }
    }
}
```

4. **Update processTelemetry (remove limit):**
```javascript
processTelemetry(telemetryArray) {
    for (const item of telemetryArray) {
        const { time, source, value } = item;

        if (this.telemetryData.hasOwnProperty(source)) {
            this.telemetryData[source].push({ time, value });

            // REMOVE THIS BLOCK (was limiting to 100 points):
            // if (this.telemetryData[source].length > this.maxDataPoints) {
            //     this.telemetryData[source].shift();
            // }
        }
    }

    this.updateCharts();
}
```

### Phase 4: Configuration

**Add to `config.py` or environment variables:**
```python
FLIGHT_LOG_DIR = "flight_logs"
MAX_FLIGHTS_TO_KEEP = 50  # Auto-delete oldest flights
ENABLE_LOGGING = True
```

---

## File Format Specification

### CSV Format (Raw Telemetry)
```csv
timestamp,cur_time,gps_lat,gps_lng,gps_alt,accel_x,accel_y,accel_z,...
2025-11-02T14:30:00.123,12453,401234567,-1051234567,1523000,15.2,...
2025-11-02T14:30:00.623,12953,401234570,-1051234565,1524500,16.1,...
```

### JSON Format (Processed for Reload)
```json
{
  "session_id": "2025-11-02_14-30-00",
  "start_time": "2025-11-02T14:30:00.000Z",
  "data": [
    {"time": 12.453, "source": "altitude", "value": 487.3},
    {"time": 12.453, "source": "velocity", "value": 32.5},
    ...
  ]
}
```

---

## Testing Plan

1. **Test data persistence:**
   - Start server, collect telemetry
   - Refresh browser → verify data restored
   - Check files created in `flight_logs/`

2. **Test reset:**
   - Click reset button
   - Verify new session started
   - Verify old session file saved
   - Verify charts cleared

3. **Test storage limits:**
   - Run mock telemetry for 1+ hour
   - Verify performance with 7,200+ data points
   - Check file sizes

4. **Test Raspberry Pi:**
   - Deploy to Pi
   - Verify SD card writes working
   - Check disk space monitoring
   - Test with actual radio hardware

---

## Decision Points

### 1. File Format
**Options:**
- CSV only (simple, universally readable)
- JSON only (easier to reload)
- **Both (RECOMMENDED)**: CSV for archival/analysis, JSON for fast reload

### 2. Session Start Trigger
**Options:**
- Auto-start on server boot (simple)
- Manual "Start New Flight" button (user control)
- **Both (RECOMMENDED)**: Auto-start, but provide manual reset

### 3. Data Retention
**Options:**
- Keep all flights forever
- **Auto-delete old flights** (keep last 50, configurable)
- Manual cleanup

### 4. Historical Flight Viewer
**Phase 1:** Just save files for external analysis
**Phase 2 (Future):** Build UI to load/replay past flights

---

## Success Criteria

- ✅ All telemetry data stored to disk in real-time
- ✅ Data survives page refreshes
- ✅ Manual reset creates new flight session
- ✅ CSV files readable in Excel/Python
- ✅ Performance acceptable with 10,000+ data points
- ✅ Works on Raspberry Pi
- ✅ Disk space managed (old flights cleaned up)

---

## Timeline Estimate

- **Backend storage module**: 2-3 hours
- **API endpoints**: 1 hour
- **Frontend integration**: 1-2 hours
- **Testing**: 1 hour
- **Total**: 5-7 hours

---

## Dependencies for Tasks 1 & 2

Once this is implemented:
- **Task 1** (Fullscreen modal) can access all data points for hover tooltips
- **Task 2** (Reset button) can call `/telemetry/reset` endpoint

**This task must be completed first.**
