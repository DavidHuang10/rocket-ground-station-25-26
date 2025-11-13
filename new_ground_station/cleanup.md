# Code Cleanup Recommendations

This document identifies outdated, unused, or overly complex code that should be cleaned up. Items are prioritized by impact.

---

## High Priority (Should Remove/Update)

### 1. **config.py - Entirely Unused Backend Config System**
**Location:** `config.py` (entire file, 95 lines)

**Issue:**
- Entire file is commented out with "NOT USED YET" at the top
- Backend Pydantic models for config management (`FieldMetadata`, `PanelConfig`, `TelemetryConfig`)
- Frontend handles all config via `public/config.json` directly
- This was a Python-based config system that never got used

**Recommendation:**
- **DELETE** the entire file
- Update CLAUDE.md to remove references to config.py being unused
- Remove commented import in `utils.py:5`

**Impact:** Reduces confusion, removes 95 lines of dead code

---

### 2. **storage.py - Unused `reset_csv()` Method**
**Location:** `storage.py:79-92` (FlightSession class)

**Issue:**
- `reset_csv()` method truncates CSV and rewrites headers
- Never called anywhere in codebase after storage update
- Old behavior from before we implemented non-destructive clear
- `clear_data()` now creates a NEW session instead of resetting the CSV

**Recommendation:**
- **DELETE** the `reset_csv()` method
- This was the old destructive approach, no longer needed

**Impact:** Removes 14 lines of unused code

---

### 3. **utils.py - Commented Config Cache Code**
**Location:** `utils.py:10-19`

**Issue:**
- Commented-out global config cache and `get_config()` function
- Comment says "Wasn't used, config is handled with frontend."
- Related to the unused `config.py` file

**Recommendation:**
- **DELETE** lines 5, 10-19 (commented import and cache code)
- Clean up the file header

**Impact:** Removes 11 lines of commented code

---

## Medium Priority (Refactor/Simplify)

### 4. **test_broadcaster.py - Outdated Tests**
**Location:** `test_broadcaster.py` (entire file, 56 lines)

**Issue:**
- Tests for `format_for_frontend()` but doesn't test with `takeoff_offset` parameter (new in storage update)
- Imports `format_for_frontend` from `main` but it's actually in `utils`
- Import of `broadcast_telemetry` is unnecessary and may not work standalone

**Recommendation:**
- **UPDATE** test to include time adjustment testing:
  ```python
  def test_format_with_offset():
      # Test without offset
      result = format_for_frontend(telemetry)
      assert result[0]["time"] == 12.0

      # Test with offset (simulate T+0 at 5s)
      result = format_for_frontend(telemetry, takeoff_offset=5.0)
      assert result[0]["time"] == 7.0  # 12.0 - 5.0
  ```
- Fix imports to use `from utils import format_for_frontend`

**Impact:** Ensures test coverage for new functionality

---

### 5. **storage.py - Redundant `clear_buffer()` Calls**
**Location:** `storage.py:267, 341`

**Issue:**
- `clear_data()` and `save_and_clear()` both call `self.current_session.clear_buffer()`
- Then immediately create a new session: `self.current_session = FlightSession(...)`
- The new session has an empty buffer anyway, so clearing the old one is redundant

**Recommendation:**
- **REMOVE** the `clear_buffer()` calls before creating new session
- Just close the old session and create new one
- Keep the method for potential future use

**Impact:** Minor simplification, removes 2 redundant operations

---

### 6. **utils.py - Large Hardcoded Field List in `format_for_frontend()`**
**Location:** `utils.py:40-70` (30 lines)

**Issue:**
- Hardcoded list of 29 fields returned as array
- Every field has identical structure: `{"time": time, "source": "...", "value": ...}`
- Not really "complex" but could be made more maintainable

**Recommendation:**
- **REFACTOR** to use a field mapping dict (optional, only if adding fields becomes frequent):
  ```python
  FIELD_MAPPING = {
      "cur_time": lambda t: t.cur_time,
      "altitude": lambda t: t.altitude,
      # ... etc
  }

  return [
      {"time": time, "source": source, "value": getter(telemetry)}
      for source, getter in FIELD_MAPPING.items()
  ]
  ```
- **OR** keep as-is since it's explicit and easy to understand

**Impact:** Debatable - explicit is sometimes better than clever

---

## Low Priority (Documentation/Naming)

### 7. **storage_update.md - Implementation Plan Now Complete**
**Location:** `storage_update.md` (530 lines)

**Issue:**
- This was the design document for the storage update
- Implementation is now complete (Phases 1-5 done)
- Still useful as historical reference and for understanding design decisions
- Could be confusing to future developers ("is this TODO or done?")

**Recommendation:**
- **RENAME** to `storage_design_notes.md` or move to `docs/` folder
- Add header noting "IMPLEMENTATION COMPLETE - This is historical design documentation"
- **OR** keep as-is if you want to implement Phases 6-7 (field endpoint, UI polish)

**Impact:** Reduces confusion about project status

---

### 8. **CLAUDE.md - Outdated File Purposes Table**
**Location:** `CLAUDE.md` (line ~195)

**Issue:**
- File change checklist and "File Purposes" table still references old behavior
- Says `config.py` is "unused" but doesn't suggest deleting it
- Doesn't mention new `backups/` folder or storage update features

**Recommendation:**
- **UPDATE** CLAUDE.md sections:
  - Add `backups/` to directory structure
  - Update "File Purposes" table to remove `config.py`
  - Add note about time adjustment and takeoff offset tracking
  - Update "Common Tasks" to reflect new clear/save behavior

**Impact:** Keeps documentation accurate for future Claude sessions

---

### 9. **main.py - `inject_telemetry` Endpoint Takes String Instead of JSON**
**Location:** `main.py:150-164`

**Issue:**
- Endpoint is `@app.post("/telemetry/inject")` with parameter `csv_data: str`
- Should use proper request body: `class InjectRequest(BaseModel): csv_data: str`
- Currently would fail with proper JSON POST

**Recommendation:**
- **UPDATE** to use Pydantic request model:
  ```python
  class InjectRequest(BaseModel):
      csv_data: str

  @app.post("/telemetry/inject")
  async def inject_telemetry(request: InjectRequest):
      csv_data = request.csv_data
      # ... rest of function
  ```

**Impact:** Makes testing endpoint usable with proper HTTP clients

---

### 10. **main.js - `loadCurrentSession()` Doesn't Use Session Metadata**
**Location:** `public/main.js:323-341`

**Issue:**
- Loads `result.session` with takeoff info (offset, takeoff_time, packet_count)
- Stores in `this.sessionInfo` but only uses `packet_count` for display
- Takeoff offset and time are not shown anywhere in UI
- Could be useful for late-joining clients to know if flight is in progress

**Recommendation:**
- **ENHANCE** to display session info:
  - Show "Flight in progress (T+45s)" if `takeoff_offset` exists
  - Show "Pre-flight idle" if `takeoff_offset` is null
  - Display in session-info section
- **OR** keep as-is if UI clutter is a concern (optional Phase 7 feature)

**Impact:** Better UX for late-joining clients

---

## Summary Statistics

| Category | Files | Lines to Remove | Lines to Add/Update |
|----------|-------|-----------------|---------------------|
| High Priority | 3 files | ~120 lines | 0 lines |
| Medium Priority | 3 files | ~2 lines | ~30 lines (tests) |
| Low Priority | 3 files | 0 lines | ~50 lines (docs/features) |

**Total dead code to remove:** ~120 lines
**Codebase size:** ~2,068 lines
**Dead code percentage:** ~5.8%

---

## Recommended Cleanup Order

1. **Delete** `config.py` (entire file)
2. **Delete** commented code in `utils.py` (lines 5, 10-19)
3. **Delete** `reset_csv()` in `storage.py` (lines 79-92)
4. **Update** tests in `test_broadcaster.py` (add offset tests)
5. **Update** CLAUDE.md (reflect new storage system)
6. **Consider** renaming `storage_update.md` to mark as complete
7. **Optional** Fix `inject_telemetry` endpoint to use proper JSON
8. **Optional** Enhance UI to show session metadata

---

## Non-Issues (Things That Look Complex But Are Fine)

### ✅ `format_for_frontend()` - Large Field List
While it's 30 lines of similar code, it's explicit, maintainable, and matches the 29-field CSV format. No cleanup needed.

### ✅ `mock_telemetry_producer()` - Mock Data Generator
Clearly labeled as mock/testing code. Will be replaced with real LoRa serial reading eventually. Keep as-is for testing.

### ✅ `FlightSession._write_csv_header()` and `_append_csv_row()`
These are long but necessary - they explicitly map all 29 fields to CSV. Keep as-is.

### ✅ Frontend manual timer code
Works well, not overly complex. No cleanup needed.

---

## Notes

- No security issues found
- No obvious performance bottlenecks
- Code style is consistent
- Error handling is reasonable
- Most complexity is inherent to the domain (29 telemetry fields, CSV parsing, WebSocket management)
