# Takeout Loop Prompts

A prompt and its resulting execution path are a unit — they version together.
Each entry names the prompt, records the path it produced, and notes what changed.
The script prints a machine-readable `PATH` JSON block at the end of every run;
the loop agent reads that to fill in "Actual path" and update findings.

---

## v1 — first clean attempt after known-bug fixes

**Status:** ready to run (2026-04-21 morning)

**Changes from baseline:**
- Fixed history checkbox selector: `'watch history'` → `'history'`
- Added scroll-to-top + 1.5s wait before "Deselect all"
- All interactive clicks now use CDP `mousePressed`/`mouseReleased` (not `.click()`)
- Added pre-flight check for in-progress export
- Script emits structured `PATH` JSON for loop recording

**Prompt:**
```
/loop Run the Google Takeout automation: browser-harness < request_takeout.py

After each run:
1. Read the PATH JSON printed at the end of the script output
2. Record the actual path in docs/takeout-loop-prompts.md under the current version's "Actual path"
3. Note the outcome (success / rate_limited / new_error / other)
4. If the outcome is NOT success:
   - Add findings to docs/findings.md
   - Fix the specific failing step in request_takeout.py
   - Increment the prompt version in docs/takeout-loop-prompts.md and document what changed
   - Sleep 30 minutes if the outcome was rate_limited, then retry
   - Otherwise retry immediately
5. Stop when outcome is "success" AND the confirmed export screen is visible in the final screenshot
```

**Expected path:**
```json
[
  {"step": "preflight",         "result": "ok"},
  {"step": "open_takeout",      "result": "ok"},
  {"step": "deselect_all",      "result": "ok", "verified": true},
  {"step": "check_youtube",     "result": "ok", "checked": true, "counter": "1 of 83 selected"},
  {"step": "open_data_options", "result": "ok"},
  {"step": "select_history",    "result": "ok"},
  {"step": "ok_modal",          "result": "ok"},
  {"step": "next_step",         "result": "ok"},
  {"step": "create_export",     "result": "success"}
]
```

**Actual path:**
```json
[
  {"step": "preflight", "result": "export_in_progress"}
]
```

**Outcome:** `new_error` — false positive in pre-flight. The script found an existing Takeout tab (left open from yesterday's session showing "82 of 83 selected") and its `text.includes('in progress')` match hit something on the page (possibly the Access Log Activity notification text). The screenshot shows the CREATE A NEW EXPORT UI, not an in-progress export confirmation. The pre-flight stopped the run prematurely.

**What changed going into v2:**
- Tightened pre-flight in-progress detection: removed broad `text.includes('in progress')` match; now only matches `'Export progress'` and `'Getting your files ready'` (specific Takeout UI strings for an active export)

---

## v2 — tightened pre-flight in-progress detection

**Status:** ready to run (2026-04-21)

**Changes from v1:**
- Pre-flight in-progress check no longer matches generic `'in progress'` substring — now only matches `'Export progress'` and `'Getting your files ready'` (strings that only appear on the actual export-in-progress screen)

**Prompt:**
```
/loop Run the Google Takeout automation: browser-harness < request_takeout.py

After each run:
1. Read the PATH JSON printed at the end of the script output
2. Record the actual path in docs/takeout-loop-prompts.md under the current version's "Actual path"
3. Note the outcome (success / rate_limited / new_error / other)
4. If the outcome is NOT success:
   - Add findings to docs/findings.md
   - Fix the specific failing step in request_takeout.py
   - Increment the prompt version in docs/takeout-loop-prompts.md and document what changed
   - Sleep 30 minutes if the outcome was rate_limited, then retry
   - Otherwise retry immediately
5. Stop when outcome is "success" AND the confirmed export screen is visible in the final screenshot
```

**Expected path:**
```json
[
  {"step": "preflight",         "result": "ok"},
  {"step": "open_takeout",      "result": "ok"},
  {"step": "deselect_all",      "result": "ok", "verified": true},
  {"step": "check_youtube",     "result": "ok", "checked": true, "counter": "1 of 83 selected"},
  {"step": "open_data_options", "result": "ok"},
  {"step": "select_history",    "result": "ok"},
  {"step": "ok_modal",          "result": "ok"},
  {"step": "next_step",         "result": "ok"},
  {"step": "create_export",     "result": "success"}
]
```

**Actual path** (final run, after multiple intra-v2 bug fixes):
```json
[
  {"step": "open_takeout",      "result": "ok"},
  {"step": "deselect_all",      "result": "ok", "verified": true},
  {"step": "check_youtube",     "result": "ok", "checked": true, "counter": "1 of 83 selected"},
  {"step": "open_data_options", "result": "ok"},
  {"step": "select_history",    "result": "not_found"},
  {"step": "ok_modal",          "result": "ok"},
  {"step": "next_step",         "result": "ok"},
  {"step": "create_export",     "result": "unknown"}
]
```

**Outcome:** `success` (actual) / `unknown` (detected) — export WAS confirmed. Screenshot 08-final shows "Export progress: Google is creating a copy of data from YouTube and YouTube Music. Created: April 21, 2026, 8:46 AM." Export includes ALL YouTube data (not just history) because the history modal selector failed. Detection missed success because page says "You'll receive an email when your export is done" not "we'll email you".

**Intra-v2 bugs discovered and fixed:**
- `find_pos` NameError: exec() functions cannot call sibling functions → fixed by inlining find_pos into click_text
- `_json` NameError inside click_text: exec() module-level imports not visible in functions → fixed with `import json as _j` inside function  
- YouTube checkbox timing: scrollIntoView + getBoundingClientRect in same JS call returned pre-scroll position → fixed by splitting into two separate calls with wait between
- Success detection false positive: `"export progress"` appears in wizard step accordion label → removed; export still submitted correctly

**What changed going into v3:**
- Success detection: removed `"export progress"` match; added `"receive an email"` and `"creating a copy"` to match the actual confirmation screen text
- Pre-flight: also detect `"creating a copy of data"` state (what the active-export screen shows)
- History selector: use grandparent element lookup to find text in sibling span (modal uses div structure, not li/label)
- Add `preflight: ok` to PATH on clean pass (currently only recorded on failure)

---

## v3 — fixed detection + history selector + pre-flight for active export

**Status:** ready for next opportunity (export currently in progress — pre-flight will gate)

**Changes from v2:**
- Success detection matches actual confirmation text: `"receive an email"`, `"creating a copy of data"`
- Pre-flight also detects active export via `"creating a copy of data"` (the live export screen phrase)
- History modal selector: uses grandparent container instead of parent to find label text (modal uses div/span not li)
- `PATH` records `preflight: ok` on clean pass

**Prompt:**
```
/loop Run the Google Takeout automation: browser-harness < request_takeout.py

After each run:
1. Read the PATH JSON printed at the end of the script output
2. Record the actual path in docs/takeout-loop-prompts.md under the current version's "Actual path"
3. Note the outcome (success / rate_limited / new_error / other)
4. If the outcome is NOT success:
   - Add findings to docs/findings.md
   - Fix the specific failing step in request_takeout.py
   - Increment the prompt version in docs/takeout-loop-prompts.md and document what changed
   - Sleep 30 minutes if the outcome was rate_limited, then retry
   - Otherwise retry immediately
5. Stop when outcome is "success" AND the confirmed export screen is visible in the final screenshot
```

**Expected path:**
```json
[
  {"step": "preflight",         "result": "ok"},
  {"step": "open_takeout",      "result": "ok"},
  {"step": "deselect_all",      "result": "ok", "verified": true},
  {"step": "check_youtube",     "result": "ok", "checked": true, "counter": "1 of 83 selected"},
  {"step": "open_data_options", "result": "ok"},
  {"step": "select_history",    "result": "ok"},
  {"step": "ok_modal",          "result": "ok"},
  {"step": "next_step",         "result": "ok"},
  {"step": "create_export",     "result": "success"}
]
```

**Actual path:** *(filled in after run)*

**Outcome:** *(filled in after run)*

**What changed going into v4:** *(filled in if v3 doesn't succeed)*
