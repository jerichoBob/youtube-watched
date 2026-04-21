---
version: 1
name: takeout-automation
display_name: "Google Takeout Automation"
status: draft
created: 2026-04-20
depends_on: []
tags: [browser-harness, cdp, google, takeout]
---

# Google Takeout Automation

## Why (Problem Statement)

> As a user, I want to reliably request a Google Takeout export of my YouTube watch history so that I can process it locally without manual browser interaction.

### Context

- Google removed watch history from the YouTube Data API — scraping myactivity.google.com was the workaround, but it's fragile with 2FA and bot detection
- Google Takeout is the official data export path and produces a clean `watch-history.json`
- `request_takeout.py` uses browser-harness (CDP) to automate the Takeout flow against an already-logged-in Chrome session — no login automation needed
- Multiple runs in initial development hit "Please try to create your export again" due to repeated `Create export` clicks and a wrong checkbox selector
- Full findings in `docs/findings.md`; versioned prompt+path attempts in `docs/takeout-loop-prompts.md`

---

## What (Requirements)

### Acceptance Criteria

- AC-1: Running `browser-harness < request_takeout.py` on a logged-in Chrome results in a confirmed Takeout export screen (no error message)
- AC-2: Only YouTube watch history is selected (1 of 83 services, 1 data type)
- AC-3: Script is idempotent — safe to re-run without triggering rate limits if no export is in progress
- AC-4: Screenshots saved to `/tmp/takeout-*.png` at each step for debugging
- AC-5: Script completes without manual intervention (no `input()` prompts)

### Out of Scope

- Downloading or parsing the export ZIP (covered in v2)
- Handling a not-logged-in Chrome session

---

## How (Approach)

### Phase 1: Fix known bugs in request_takeout.py

- Fix history checkbox selector: change `.includes('watch history')` → `.includes('history')` in modal search
- Add scroll-to-top + 2s wait before "Deselect all" click to ensure element is in viewport
- Fix exec() closure issue: all helper functions must use `global` for mutable state, no nested function calls

### Phase 2: Validate clean run sequence

- Reload page fresh before each attempt
- Verify "0 of 83 selected" after deselect all
- Verify `cb.checked === true` and "1 of 83 selected" after YouTube checkbox click
- Verify modal opens after clicking options button
- Verify history checkbox is checked in modal before clicking OK
- Verify step 2 accordion expands after "Next step"
- Click "Create export" exactly once

### Phase 3: Harden and document

- Add pre-flight check: if an export is already in progress, print status and exit cleanly
- Update `docs/takeout-loop-prompts.md` with actual path taken and outcome
- Update `CLAUDE.md` with final run instructions

---

## Technical Notes

### Dependencies

- `browser-harness` installed at `~/pgh/browser-harness` via `uv tool install -e .`
- Chrome with remote debugging enabled (one-time setup via `chrome://inspect/#remote-debugging`)
- User must be logged into Google in Chrome before running

### Key DOM Selectors (as of 2026-04-20)

- YouTube checkbox: `input[name="YouTube and YouTube Music"]`
- Options button innerText: contains `'type selected'` or `'YouTube data included'`
- Modal scope: last `[role="dialog"]` in document
- History label: `.includes('history')` (not `'watch history'`)
- All interactive elements require CDP `mousePressed`/`mouseReleased` — plain `.click()` does not trigger Material Design jscontroller

### Risks & Mitigations

| Risk | Mitigation |
| ---- | ---------- |
| Google rate-limits repeated export requests | Check for in-progress export before attempting; sleep 30 min between /loop retries |
| DOM selectors change after Google UI update | Screenshots at every step make failures immediately visible |
| exec() closure bugs in browser-harness | Keep all logic flat; no helper calling helper |

---

## Open Questions

1. How long does Google's "please try again" rate limit last? (Estimate: a few hours)
2. Does Google throttle per-session or per-account?

---

## Changelog

| Date       | Change        |
| ---------- | ------------- |
| 2026-04-20 | Initial draft |
