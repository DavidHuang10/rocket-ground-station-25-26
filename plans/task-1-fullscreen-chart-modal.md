# Task 1: Fullscreen Chart Modal

**Priority:** 2 (After data persistence)
**Status:** Planning
**Dependencies:** Task 3 (Data Persistence Strategy)

---

## Overview

Implement a fullscreen modal overlay that displays a larger version of any chart when clicked, with hover tooltips showing exact time and value for each data point.

---

## Problem Statement

**Current limitations:**
- Charts are small in the dashboard grid
- Hard to see detailed values
- No zoom or detailed inspection capability
- No way to see exact values at specific timestamps

**Requirements:**
- Click any chart → opens fullscreen
- Larger chart for better visibility
- Hover tooltips show exact time + value
- Easy to close (ESC key or X button)
- Smooth UI/UX experience

---

## User Experience Flow

1. User clicks on any chart panel
2. Modal overlay covers entire screen (dark semi-transparent background)
3. Large version of chart displayed in center
4. User hovers mouse → tooltip shows exact data point
5. User presses ESC or clicks X button → modal closes
6. User clicks outside modal → modal closes

---

## Design Mockup

```
┌────────────────────────────────────────────────────────┐
│                    [Dark Overlay 80% opacity]          │
│                                                        │
│  ┌──────────────────────────────────────────────┐    │
│  │  Altitude (m AGL)                      [X]   │    │
│  │  ┌────────────────────────────────────────┐ │    │
│  │  │                                        │ │    │
│  │  │        [Large Chart with hover]      │ │    │
│  │  │                                        │ │    │
│  │  │        Tooltip: Time: 45.2s           │ │    │
│  │  │                 Value: 487.3 m        │ │    │
│  │  │                                        │ │    │
│  │  └────────────────────────────────────────┘ │    │
│  │  Current Value: 487.3 m                    │    │
│  └──────────────────────────────────────────────┘    │
│                                                        │
│           [Click outside or ESC to close]            │
└────────────────────────────────────────────────────────┘
```

---

## Implementation Plan

### Phase 1: Add Modal to HTML

**Modify `index.html`:**

Add modal structure inside `<div id="app">`:

```html
<!-- Fullscreen Chart Modal -->
<div v-if="fullscreenChart" class="chart-modal" @click.self="closeFullscreen">
    <div class="modal-content">
        <div class="modal-header">
            <h2>{{ fullscreenChart.title }}</h2>
            <button class="close-btn" @click="closeFullscreen">&times;</button>
        </div>
        <div class="modal-body">
            <canvas :id="`fullscreen-chart`" ref="fullscreenCanvas"></canvas>
            <div class="modal-current-value">
                Current: {{ formatValue(getCurrentValue(fullscreenChart.fields[0]), fullscreenChart.precision) }}
                {{ fullscreenChart.unit }}
            </div>
        </div>
    </div>
</div>
```

**Update chart panel click handler:**

```html
<!-- Chart -->
<div v-else-if="panel.type === 'chart'"
     class="panel chart-panel clickable"
     @click="openFullscreen(panel)">
    <h2>{{ panel.title }}</h2>
    <canvas :id="`chart-${panel.id}`"></canvas>
    <div class="current-value">
        {{ formatValue(getCurrentValue(panel.fields[0]), panel.precision) }} {{ panel.unit }}
    </div>
</div>
```

---

### Phase 2: Add CSS Styling

**Modify `style.css`:**

```css
/* Fullscreen Chart Modal */
.chart-modal {
    position: fixed;
    top: 0;
    left: 0;
    width: 100vw;
    height: 100vh;
    background-color: rgba(0, 0, 0, 0.85);
    display: flex;
    justify-content: center;
    align-items: center;
    z-index: 9999;
    animation: fadeIn 0.2s ease-in-out;
}

@keyframes fadeIn {
    from { opacity: 0; }
    to { opacity: 1; }
}

.modal-content {
    background: #1e1e1e;
    border-radius: 12px;
    width: 90vw;
    height: 85vh;
    max-width: 1400px;
    display: flex;
    flex-direction: column;
    box-shadow: 0 10px 50px rgba(0, 0, 0, 0.5);
    animation: slideUp 0.3s ease-out;
}

@keyframes slideUp {
    from {
        transform: translateY(50px);
        opacity: 0;
    }
    to {
        transform: translateY(0);
        opacity: 1;
    }
}

.modal-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 20px 30px;
    border-bottom: 2px solid #333;
}

.modal-header h2 {
    margin: 0;
    font-size: 28px;
    color: #fff;
}

.close-btn {
    background: none;
    border: none;
    color: #fff;
    font-size: 40px;
    cursor: pointer;
    line-height: 1;
    padding: 0;
    width: 40px;
    height: 40px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 4px;
    transition: background-color 0.2s;
}

.close-btn:hover {
    background-color: rgba(255, 255, 255, 0.1);
}

.modal-body {
    flex: 1;
    padding: 30px;
    display: flex;
    flex-direction: column;
    overflow: hidden;
}

.modal-body canvas {
    flex: 1;
    width: 100% !important;
    height: 100% !important;
}

.modal-current-value {
    text-align: center;
    font-size: 24px;
    font-weight: bold;
    color: #4caf50;
    margin-top: 20px;
    padding: 15px;
    background: rgba(76, 175, 80, 0.1);
    border-radius: 8px;
}

/* Make chart panels clickable */
.chart-panel.clickable {
    cursor: pointer;
    transition: transform 0.2s, box-shadow 0.2s;
}

.chart-panel.clickable:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(76, 175, 80, 0.3);
}

.chart-panel.clickable:active {
    transform: translateY(0);
}
```

---

### Phase 3: Add JavaScript Logic

**Modify `main.js`:**

1. **Add data properties:**

```javascript
data() {
    return {
        // ... existing properties
        fullscreenChart: null,
        fullscreenChartInstance: null
    };
}
```

2. **Add methods:**

```javascript
methods: {
    // ... existing methods

    openFullscreen(panel) {
        this.fullscreenChart = panel;

        // Wait for DOM update, then create chart
        this.$nextTick(() => {
            this.createFullscreenChart();
        });
    },

    closeFullscreen() {
        // Destroy chart instance
        if (this.fullscreenChartInstance) {
            this.fullscreenChartInstance.destroy();
            this.fullscreenChartInstance = null;
        }

        this.fullscreenChart = null;
    },

    createFullscreenChart() {
        const panel = this.fullscreenChart;
        const canvas = this.$refs.fullscreenCanvas;

        if (!canvas) return;

        // Get data for this chart
        const field = panel.fields[0];
        const data = (this.telemetryData[field] || []).map(d => ({ x: d.time, y: d.value }));

        // Create chart with tooltips enabled
        this.fullscreenChartInstance = new Chart(canvas, {
            type: 'line',
            data: {
                datasets: [{
                    label: panel.title,
                    data: data,
                    borderColor: panel.chart_color || '#4caf50',
                    backgroundColor: this.hexToRgba(panel.chart_color || '#4caf50', 0.1),
                    tension: 0.4,
                    pointRadius: 2,  // Small dots
                    pointHoverRadius: 6  // Larger on hover
                }]
            },
            options: this.getFullscreenChartOptions(panel)
        });
    },

    getFullscreenChartOptions(panel) {
        return {
            responsive: true,
            maintainAspectRatio: false,
            animation: false,
            interaction: {
                mode: 'nearest',
                intersect: false,
                axis: 'x'
            },
            scales: {
                x: {
                    type: 'linear',
                    title: {
                        display: true,
                        text: 'Time (s)',
                        font: {
                            size: 16
                        }
                    },
                    ticks: {
                        autoSkip: true,
                        maxTicksLimit: 15,
                        font: {
                            size: 14
                        }
                    },
                    grid: {
                        color: 'rgba(255, 255, 255, 0.1)'
                    }
                },
                y: {
                    title: {
                        display: true,
                        text: `${panel.title} (${panel.unit || ''})`,
                        font: {
                            size: 16
                        }
                    },
                    ticks: {
                        autoSkip: true,
                        maxTicksLimit: 12,
                        font: {
                            size: 14
                        }
                    },
                    grid: {
                        color: 'rgba(255, 255, 255, 0.1)'
                    }
                }
            },
            plugins: {
                legend: {
                    display: false
                },
                tooltip: {
                    enabled: true,
                    backgroundColor: 'rgba(0, 0, 0, 0.8)',
                    titleColor: '#fff',
                    bodyColor: '#fff',
                    borderColor: panel.chart_color || '#4caf50',
                    borderWidth: 2,
                    padding: 12,
                    displayColors: false,
                    titleFont: {
                        size: 16,
                        weight: 'bold'
                    },
                    bodyFont: {
                        size: 14
                    },
                    callbacks: {
                        title: (context) => {
                            const time = context[0].parsed.x;
                            return `Time: ${time.toFixed(3)} s`;
                        },
                        label: (context) => {
                            const value = context.parsed.y;
                            return `${panel.title}: ${value.toFixed(panel.precision || 2)} ${panel.unit || ''}`;
                        }
                    }
                }
            }
        };
    }
}
```

3. **Add keyboard handler:**

```javascript
mounted() {
    // ... existing mounted code

    // Add ESC key handler for modal
    window.addEventListener('keydown', this.handleKeydown);
},

beforeUnmount() {
    // ... existing cleanup

    // Remove keyboard listener
    window.removeEventListener('keydown', this.handleKeydown);
},

methods: {
    // ... other methods

    handleKeydown(e) {
        if (e.key === 'Escape' && this.fullscreenChart) {
            this.closeFullscreen();
        }
    }
}
```

4. **Update fullscreen chart when new data arrives:**

```javascript
updateCharts() {
    // Update regular charts
    this.config.panels.forEach(panel => {
        const chart = this._charts[panel.id];
        if (chart) {
            const field = panel.fields[0];
            const data = (this.telemetryData[field] || []).map(d => ({ x: d.time, y: d.value }));
            chart.data.datasets[0].data = data;
            chart.update('none');
        }
    });

    // Update fullscreen chart if open
    if (this.fullscreenChartInstance && this.fullscreenChart) {
        const field = this.fullscreenChart.fields[0];
        const data = (this.telemetryData[field] || []).map(d => ({ x: d.time, y: d.value }));
        this.fullscreenChartInstance.data.datasets[0].data = data;
        this.fullscreenChartInstance.update('none');
    }
}
```

---

## Tooltip Configuration Details

### Chart.js Tooltip Features

The tooltip will show:
- **Title**: Time value (e.g., "Time: 45.234 s")
- **Body**: Data value with unit (e.g., "Altitude: 487.3 m")
- **Styling**: Dark background, colored border matching chart color
- **Interaction**: Follows mouse, shows nearest data point
- **Performance**: Uses 'nearest' mode for smooth tracking

### Tooltip Behavior

- **Hover anywhere on chart** → shows nearest data point
- **Large fonts** for readability (16px title, 14px body)
- **High precision** in time display (3 decimal places = millisecond accuracy)
- **Formatted values** using panel's precision setting

---

## Mobile/Touch Support

For touch devices:
- Tap chart → open fullscreen
- Tap and hold data point → show tooltip
- Two-finger pinch → close modal
- Single tap outside → close modal

---

## Performance Considerations

### Large Datasets

With unlimited data storage (from Task 3), charts may have 10,000+ points:
- **Point radius: 0** on regular charts (no dots drawn)
- **Point radius: 2** on fullscreen (small dots for hover targets)
- **Decimation**: Chart.js automatically reduces points for performance
- **Update mode: 'none'**: Skips animations for faster updates

### Memory Management

- Only one fullscreen chart exists at a time
- Destroyed when modal closes (prevents memory leaks)
- Regular charts persist, fullscreen is temporary

---

## Testing Plan

1. **Basic functionality:**
   - Click each chart type → verify fullscreen opens
   - Hover over data points → verify tooltip shows
   - Press ESC → verify modal closes
   - Click X button → verify modal closes
   - Click outside modal → verify modal closes

2. **Data accuracy:**
   - Verify tooltip shows correct time values
   - Verify tooltip shows correct data values with proper precision
   - Verify units displayed correctly

3. **Performance:**
   - Test with 1,000 data points
   - Test with 10,000 data points
   - Verify smooth hover interaction
   - Verify no lag when updating with new data

4. **Edge cases:**
   - Open fullscreen with empty data
   - Open fullscreen, receive new data → verify chart updates
   - Open multiple fullscreens rapidly (shouldn't crash)
   - Resize window with fullscreen open

5. **Mobile:**
   - Test on tablet/phone
   - Verify touch interactions work
   - Verify responsive sizing

---

## Future Enhancements (Optional)

1. **Crosshair cursor**: Vertical line following mouse
2. **Multiple tooltips**: Show all fields at same timestamp
3. **Export chart**: Download as PNG image
4. **Compare mode**: Overlay multiple charts
5. **Time range selector**: Zoom to specific time window
6. **Annotations**: Mark important events (launch, apogee, etc.)

---

## Success Criteria

- ✅ Click any chart → fullscreen modal opens
- ✅ Modal shows larger chart with same data
- ✅ Hover shows tooltip with exact time + value
- ✅ ESC key closes modal
- ✅ X button closes modal
- ✅ Click outside closes modal
- ✅ Chart updates in real-time while fullscreen
- ✅ Smooth animations and transitions
- ✅ Works on desktop and mobile
- ✅ No performance issues with large datasets

---

## Timeline Estimate

- **HTML structure**: 30 minutes
- **CSS styling**: 1 hour
- **JavaScript logic**: 2 hours
- **Tooltip configuration**: 30 minutes
- **Testing**: 1 hour
- **Total**: 5 hours

---

## Dependencies

**Requires Task 3 (Data Persistence) to be completed:**
- Need unlimited data storage for hover to work on all points
- If limited to 100 points, fullscreen chart would have gaps

**Blocks Task 2:**
- No blocking, can be done in parallel with reset button
