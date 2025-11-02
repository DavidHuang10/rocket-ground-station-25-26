# Task 2: Manual Reset Button

**Priority:** 3 (After data persistence and modal)
**Status:** Planning
**Dependencies:** Task 3 (Data Persistence Strategy)

---

## Overview

Add a manual "Reset Charts" button that clears all telemetry data and starts a new flight session, giving operators full control over when to start recording a new flight.

---

## Problem Statement

**Current limitations:**
- No way to clear accumulated data between test runs
- Charts continuously accumulate data from server start
- Need manual control to start fresh for each flight/test

**Requirements:**
- Prominent "Reset" button in dashboard
- Clears all chart data
- Starts new flight session on backend
- Confirmation dialog to prevent accidental resets
- Visual feedback when reset occurs

---

## User Experience Flow

1. User clicks "Reset Charts" button
2. Confirmation dialog appears: "Start new flight session? This will clear all current data."
3. User confirms:
   - Backend creates new flight session
   - Frontend clears all telemetry arrays
   - Charts reset to empty state
   - Session ID updates
   - Success message shown (optional)
4. User cancels:
   - No action taken
   - Dialog closes

---

## Design Options

### Option A: Single Reset Button (RECOMMENDED)

```
┌──────────────────────────────────────────────┐
│  ERIS Delta Ground Station    Connected ●   │
├──────────────────────────────────────────────┤
│  Port: [8000]  [Reconnect]  [Reset Charts]  │
└──────────────────────────────────────────────┘
```

**Pros:**
- Simple, obvious placement
- One-click access
- Matches existing button style

**Cons:**
- Could be clicked accidentally

### Option B: Reset with Confirmation Icon

```
┌──────────────────────────────────────────────┐
│  ERIS Delta Ground Station    Connected ●   │
├──────────────────────────────────────────────┤
│  Port: [8000]  [Reconnect]  [⟳ Reset All]  │
└──────────────────────────────────────────────┘
```

**Pros:**
- Icon makes purpose clearer
- Visually distinct

**Cons:**
- Takes more space

### Option C: Separate Control Section

```
┌──────────────────────────────────────────────┐
│  ERIS Delta Ground Station    Connected ●   │
├──────────────────────────────────────────────┤
│  Connection:                                 │
│    Port: [8000]  [Reconnect]               │
│                                              │
│  Flight Session: 2025-11-02_14-30-00       │
│    [Reset Charts]  [Download Data]          │
└──────────────────────────────────────────────┘
```

**Pros:**
- Organized by function
- Room for future features (download, etc.)
- Shows current session ID

**Cons:**
- Takes more vertical space
- More complex layout

**Recommendation: Option A** - Simple and effective for now, can evolve to Option C later.

---

## Implementation Plan

### Phase 1: Add Reset Button to HTML

**Modify `index.html`:**

Update controls section:

```html
<div class="controls">
    <label>
        WebSocket Port:
        <input type="number" v-model="port" min="1" max="65535">
    </label>
    <button @click="reconnect">Reconnect</button>
    <button @click="resetCharts" class="reset-btn">Reset Charts</button>

    <!-- Optional: Show session info -->
    <div v-if="sessionId" class="session-info">
        Session: {{ sessionId }}
    </div>
</div>
```

---

### Phase 2: Add CSS Styling

**Modify `style.css`:**

```css
/* Reset button styling */
.reset-btn {
    background-color: #f44336;  /* Red for warning */
    color: white;
    border: none;
    padding: 10px 20px;
    border-radius: 4px;
    cursor: pointer;
    font-size: 14px;
    font-weight: 500;
    transition: background-color 0.2s, transform 0.1s;
}

.reset-btn:hover {
    background-color: #d32f2f;
    transform: translateY(-1px);
}

.reset-btn:active {
    transform: translateY(0);
}

.reset-btn:disabled {
    background-color: #999;
    cursor: not-allowed;
}

/* Session info display */
.session-info {
    display: inline-block;
    margin-left: 20px;
    padding: 8px 16px;
    background: rgba(255, 255, 255, 0.05);
    border-radius: 4px;
    font-size: 12px;
    color: #aaa;
    font-family: 'Courier New', monospace;
}

.session-info::before {
    content: '📊 ';
}
```

---

### Phase 3: Add JavaScript Logic

**Modify `main.js`:**

This method was already partially defined in Task 3 plan, here's the complete version:

```javascript
methods: {
    // ... existing methods

    async resetCharts() {
        // Confirmation dialog
        const confirmed = confirm(
            'Start new flight session?\n\n' +
            'This will:\n' +
            '• Clear all current chart data\n' +
            '• Save current session to file\n' +
            '• Start a new flight log\n\n' +
            'This action cannot be undone.'
        );

        if (!confirmed) {
            return;
        }

        try {
            // Disable button during reset
            this.isResetting = true;

            // Call backend reset endpoint
            const response = await fetch(`http://localhost:${this.port}/telemetry/reset`, {
                method: 'POST'
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            const result = await response.json();

            // Clear all frontend telemetry data
            for (const key in this.telemetryData) {
                this.telemetryData[key] = [];
            }

            // Update all charts (will show empty state)
            this.updateCharts();

            // Update session ID
            this.sessionId = result.session.session_id;

            // Log success
            console.log('✅ New flight session started:', this.sessionId);

            // Optional: Show success message to user
            // alert('New flight session started!');

        } catch (error) {
            console.error('❌ Failed to reset session:', error);
            alert(`Failed to reset charts: ${error.message}\n\nPlease check the server connection.`);
        } finally {
            this.isResetting = false;
        }
    }
}
```

**Add data property for button state:**

```javascript
data() {
    return {
        // ... existing properties
        sessionId: null,
        isResetting: false
    };
}
```

**Update button in template to show loading state:**

```html
<button
    @click="resetCharts"
    class="reset-btn"
    :disabled="isResetting || !connected">
    {{ isResetting ? 'Resetting...' : 'Reset Charts' }}
</button>
```

---

### Phase 4: Backend Endpoint (Already in Task 3)

The `/telemetry/reset` endpoint is defined in Task 3's `main.py` changes:

```python
@app.post("/telemetry/reset")
async def reset_telemetry():
    """Start a new flight session (clears current data)."""
    storage_manager.reset_session()
    return {
        "status": "success",
        "message": "New flight session started",
        "session": storage_manager.get_session_info()
    }
```

**What happens on reset:**
1. Backend saves current session to disk (CSV + JSON)
2. Creates new session with new timestamp
3. Clears in-memory telemetry buffer
4. Returns new session info to frontend
5. Frontend clears its data arrays and updates charts

---

## Enhanced Features (Optional)

### 1. Keyboard Shortcut

Add global keyboard shortcut (Ctrl+Shift+R):

```javascript
handleKeydown(e) {
    // ESC for closing fullscreen (from Task 1)
    if (e.key === 'Escape' && this.fullscreenChart) {
        this.closeFullscreen();
    }

    // Ctrl+Shift+R for reset
    if (e.ctrlKey && e.shiftKey && e.key === 'R') {
        e.preventDefault();
        this.resetCharts();
    }
}
```

### 2. Auto-disable When Disconnected

Button should be disabled when WebSocket is disconnected:

```html
<button
    @click="resetCharts"
    class="reset-btn"
    :disabled="isResetting || !connected"
    :title="!connected ? 'Reconnect to reset' : 'Start new flight session'">
    {{ isResetting ? 'Resetting...' : 'Reset Charts' }}
</button>
```

### 3. Toast Notification Instead of Alert

Use a non-blocking toast notification:

```javascript
// Add to data
data() {
    return {
        // ...
        toastMessage: null,
        toastType: 'success'  // 'success' | 'error'
    };
}

// Show toast method
showToast(message, type = 'success') {
    this.toastMessage = message;
    this.toastType = type;

    setTimeout(() => {
        this.toastMessage = null;
    }, 3000);
}

// In resetCharts success:
this.showToast('New flight session started!', 'success');

// In resetCharts error:
this.showToast('Failed to reset charts', 'error');
```

Add toast component to HTML:

```html
<!-- Toast notification -->
<div v-if="toastMessage" :class="['toast', toastType]">
    {{ toastMessage }}
</div>
```

CSS:

```css
.toast {
    position: fixed;
    bottom: 20px;
    right: 20px;
    padding: 16px 24px;
    border-radius: 8px;
    font-weight: 500;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
    z-index: 10000;
    animation: slideInRight 0.3s ease-out;
}

.toast.success {
    background-color: #4caf50;
    color: white;
}

.toast.error {
    background-color: #f44336;
    color: white;
}

@keyframes slideInRight {
    from {
        transform: translateX(400px);
        opacity: 0;
    }
    to {
        transform: translateX(0);
        opacity: 1;
    }
}
```

### 4. Reset Statistics Display

Show stats about what was reset:

```javascript
async resetCharts() {
    if (!confirm('...')) return;

    try {
        // Calculate stats before reset
        const totalDataPoints = Object.values(this.telemetryData)
            .reduce((sum, arr) => sum + arr.length, 0);

        const duration = this.getCurrentTime();  // Last timestamp

        // ... perform reset ...

        console.log(`✅ Reset complete:`);
        console.log(`   • Data points cleared: ${totalDataPoints}`);
        console.log(`   • Session duration: ${duration.toFixed(1)}s`);
        console.log(`   • New session: ${this.sessionId}`);

    } catch (error) {
        // ...
    }
}
```

---

## Confirmation Dialog Variations

### Simple (Current)
```
Start new flight session? This will clear all current data.
[Cancel] [OK]
```

### Detailed
```
Start new flight session?

This will:
• Clear all current chart data
• Save current session to file
• Start a new flight log

This action cannot be undone.

[Cancel] [OK]
```

### Custom HTML Modal (Advanced)
```html
<!-- Custom confirmation modal -->
<div v-if="showResetConfirm" class="confirm-modal" @click.self="showResetConfirm = false">
    <div class="confirm-content">
        <h3>Start New Flight Session?</h3>
        <div class="confirm-body">
            <p>This will clear all current data and start a new flight log.</p>
            <div class="confirm-stats">
                <div>Current session: {{ sessionId }}</div>
                <div>Duration: {{ formatTimer(getCurrentValue('cur_time')) }}</div>
                <div>Data points: {{ getTotalDataPoints() }}</div>
            </div>
        </div>
        <div class="confirm-actions">
            <button @click="showResetConfirm = false" class="cancel-btn">Cancel</button>
            <button @click="confirmReset" class="confirm-btn">Reset</button>
        </div>
    </div>
</div>
```

---

## Error Handling

### Scenarios to Handle

1. **Server offline**
   - Disable reset button when `!connected`
   - Show error message if server becomes unreachable during reset

2. **Network timeout**
   - Set fetch timeout (5 seconds)
   - Show "Server not responding" message

3. **Partial failure**
   - Backend reset succeeds but response fails
   - Frontend should still clear data
   - Log warning in console

4. **Rapid clicking**
   - Disable button immediately on click
   - Prevent multiple simultaneous resets

### Example with Timeout

```javascript
async resetCharts() {
    if (!confirm('...')) return;

    try {
        this.isResetting = true;

        // Create abort controller for timeout
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 5000);

        const response = await fetch(
            `http://localhost:${this.port}/telemetry/reset`,
            {
                method: 'POST',
                signal: controller.signal
            }
        );

        clearTimeout(timeoutId);

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        const result = await response.json();

        // Clear frontend data
        for (const key in this.telemetryData) {
            this.telemetryData[key] = [];
        }
        this.updateCharts();
        this.sessionId = result.session.session_id;

        console.log('✅ Reset successful:', this.sessionId);

    } catch (error) {
        if (error.name === 'AbortError') {
            alert('Reset timeout - server not responding');
        } else {
            alert(`Reset failed: ${error.message}`);
        }
        console.error('❌ Reset error:', error);
    } finally {
        this.isResetting = false;
    }
}
```

---

## Testing Plan

### Functional Tests

1. **Basic reset:**
   - Populate charts with data
   - Click reset button
   - Confirm dialog
   - Verify charts clear
   - Verify new session ID

2. **Cancel reset:**
   - Click reset button
   - Cancel dialog
   - Verify data unchanged

3. **Reset during data stream:**
   - Start receiving telemetry
   - Reset while data flowing
   - Verify clean reset
   - Verify new data appears in new session

4. **Multiple resets:**
   - Reset once
   - Add new data
   - Reset again
   - Verify each creates new session

### Error Tests

5. **Reset while disconnected:**
   - Disconnect WebSocket
   - Verify button disabled
   - Reconnect
   - Verify button enabled

6. **Server offline:**
   - Stop backend
   - Click reset
   - Verify error message
   - Verify frontend state safe

7. **Network timeout:**
   - Simulate slow network
   - Verify timeout handling
   - Verify user feedback

### UI Tests

8. **Button states:**
   - Verify normal state
   - Verify hover effect
   - Verify disabled state
   - Verify loading state

9. **Session display:**
   - Verify session ID shown
   - Verify updates after reset

### Integration Tests

10. **With Task 1 (Fullscreen):**
    - Open fullscreen chart
    - Reset
    - Verify fullscreen closes or updates

11. **With Task 3 (Storage):**
    - Reset
    - Verify old session saved to disk
    - Verify new session file created
    - Refresh browser
    - Verify new session loads

---

## Success Criteria

- ✅ Reset button visible and accessible
- ✅ Confirmation dialog prevents accidental resets
- ✅ All chart data clears on reset
- ✅ New backend session created
- ✅ New session ID displayed
- ✅ Button disabled when disconnected
- ✅ Loading state during reset
- ✅ Error handling for all failure modes
- ✅ Smooth user experience
- ✅ No data corruption or leaks

---

## Timeline Estimate

- **HTML button**: 15 minutes
- **CSS styling**: 30 minutes
- **JavaScript logic**: 1 hour
- **Error handling**: 30 minutes
- **Testing**: 1 hour
- **Total**: 3 hours

---

## Dependencies

**Requires Task 3 (Data Persistence):**
- Backend `/telemetry/reset` endpoint must exist
- Storage manager must handle session reset

**No dependencies on Task 1:**
- Can be implemented in parallel with fullscreen modal
- Should handle case where fullscreen is open during reset

---

## Future Enhancements

1. **Auto-reset on stage 0→1 transition** (original smart reset idea)
   - Keep manual button
   - Add optional auto-reset setting
   - Configurable via settings panel

2. **Download session before reset**
   - "Reset & Download" button
   - Saves CSV/JSON before clearing

3. **Session management UI**
   - List of recent sessions
   - Load previous session
   - Delete old sessions

4. **Undo reset**
   - Keep last session in memory for 30 seconds
   - "Undo" button after reset
   - Restore previous data if clicked

5. **Reset with note**
   - Add text note to session file
   - E.g., "Test flight #3 - airbrake calibration"
   - Helps identify flights later

---

## Integration Notes

### With CLAUDE.md Context

Update the project's `CLAUDE.md` to document the reset functionality:

```markdown
## Manual Reset Button

Located in dashboard header, clears all telemetry data and starts new flight session.

**When to use:**
- Before each new flight or test
- When switching between test configurations
- To clear accumulated data from multiple tests

**What happens:**
1. Confirmation dialog appears
2. Current session saved to `flight_logs/`
3. New session created with timestamp
4. All charts cleared
5. New telemetry starts fresh

**Keyboard shortcut:** Ctrl+Shift+R (optional)
```

### With README.md

Add to user documentation:

```markdown
## Resetting the Dashboard

To start a new flight session:
1. Click the **Reset Charts** button in the header
2. Confirm the action
3. All data clears and a new session begins

The previous session is automatically saved to `flight_logs/` directory.
```
