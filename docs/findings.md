# Google Takeout Automation — Findings

Attempting to automate `takeout.google.com` via `browser-harness` (CDP-based) to request a YouTube watch history export.

## What Works

- **Connecting to Chrome via CDP** — browser-harness attaches to an existing logged-in Chrome session cleanly, no login/2FA needed.
- **Deselect all** — clicking the "Deselect all" link at the top of the service list works *when the element is in the viewport*. If the page hasn't fully rendered yet or the element is off-screen, the JS text-match finds nothing. A wait + scroll-to-top before clicking is required.
- **Finding and clicking the YouTube checkbox** — JS `.querySelector('input[name="YouTube and YouTube Music"]')` reliably finds the checkbox. The checkbox requires **full CDP mouse events** (`mouseMoved` → `mousePressed` → `mouseReleased`) — a plain `.click()` call or a `li.click()` does not trigger the Material Design component's state change. After a correct CDP click, `cb.checked` becomes `true` and the counter updates to `1 of 83 selected`.
- **Opening the YouTube data-type picker** — the button shows as `"list\nAll YouTube data included"` or `"list\n1 type selected"` in `innerText`. Matching on `.includes('YouTube data included')` or `.includes('type selected')` works.
- **"Next step" button** — found and clicked successfully. The page stays at the same URL (`takeout.google.com/settings/takeout`) but advances the accordion to step 2 ("Choose file type, frequency & destination"). The URL does not change between steps.
- **"Create export" button** — located successfully at step 2. CDP click fires without error.

## What Doesn't Work (Yet)

### "Please try to create your export again"
The export submission repeatedly returns this error. Likely causes:
1. **Rate limiting / duplicate submission** — we fired `Create export` multiple times across attempts (the button was clicked 3–4 times in total across runs). Google may be throttling or blocking repeat submissions in the same session.
2. **Incomplete data selection** — in several runs the YouTube data modal's "watch history" checkbox was not found (`history_pos: None`), meaning the data type filter was left in an indeterminate state. Google may reject exports with no data types selected for a service.
3. **Session state corruption** — repeated partial interactions (deselect → re-select cycles, modal opens without confirms) may have left the server-side session in a bad state.

### Watch history checkbox inside the modal
The data-type picker modal for YouTube shows a list of checkboxes (watch history, search history, comments, etc.). The modal uses `[role="dialog"]` and the checkboxes are `input[type="checkbox"]` inside `li` elements. The label text includes "history" but the exact text varies — observed as `"history"` not `"watch history"` in the modal. The current selector `.includes('watch history')` misses it; need to also match plain `'history'`.

### "Deselect all" in the modal
Found and clicked successfully (`x:664, y:173`) but the subsequent history checkbox click fails. Likely the modal deselect resets the state correctly but the history re-select isn't landing.

### exec() closure scope
`browser-harness` runs scripts via Python's `exec()`. Functions defined in the exec scope cannot close over other functions defined in the same scope — `NameError: name 'X' is not defined` when a helper calls another helper. Workaround: inline all logic, or use `global` declarations for mutable state like lists.

## DOM Structure Notes

**YouTube service row:**
```
div.vrgBwc
  div.SmIqPb  (logo)
  div.znM4qf  (text: "YouTube and YouTube Music", description)
  div.uedLle
    div.VfPpkd-MPu53c  (Material checkbox container, jscontroller="etBPYb")
      input.VfPpkd-muHVFf-bMcfAe[type=checkbox][name="YouTube and YouTube Music"]
```
- Selector: `input[name="YouTube and YouTube Music"]`
- Bounding rect: ~40×40px, positioned to the far right of the row
- Requires CDP `mousePressed`/`mouseReleased` to trigger the jscontroller

**"Deselect all" button:**
- Top-level page link, rendered as a `DIV` (not `<a>` or `<button>`)
- Only visible when the page is scrolled near the top
- Coordinate observed: ~(903, 427) at 1328×658 viewport

**Data type modal:**
- Selector: `[role="dialog"]` — always take the last one in the list
- Checkboxes: `input[type="checkbox"]` within `li` elements
- "history" label text (not "watch history") — match `.includes('history')`

### Export confirmed (2026-04-21)
The v2 run produced a confirmed export. Screenshot 08-final shows "Export progress: Google is creating a copy of data from YouTube and YouTube Music. Created: April 21, 2026, 8:46 AM." The export includes ALL YouTube data (not just history) because the history modal selector failed. For the user's purpose this is fine — the export will contain watch history which we can parse.

### History modal selector bug (2026-04-21)
The YouTube data-type modal uses `<div>/<span>` structure, NOT `<li>/<label>`. The checkbox `input` element's `parentElement` is the Material Design checkbox container (which contains only the input and ripple elements — no text). The text "history" lives in a *sibling* `<span>`. Fix: find the element whose sole `innerText === 'history'`, then walk up to the ancestor that contains both the text and a checkbox input.

### "Export progress" false positive (2026-04-21)
The string `"Export progress"` appears as the label of step 3 in the wizard accordion, always present on the page. Cannot use it alone for in-progress export detection or success detection. Use `"creating a copy of data"` and `"receive an email"` (from the active export screen) instead.

### exec() closure scope (2026-04-21)
Two exec() scope bugs discovered:
1. `click_text` called `find_pos` (sibling function) → NameError. Fix: inline find_pos logic inside click_text.
2. `_json` imported at module level not visible inside functions. Fix: `import json as _j` at top of each function that needs it.

### YouTube checkbox timing (2026-04-21)
Combining `scrollIntoView()` and `getBoundingClientRect()` in the same JS call returns pre-scroll coordinates. Fix: separate into two JS calls with a `wait(1)` between them.

### Pre-flight false positive (2026-04-21)
The pre-flight check `text.includes('in progress')` is too broad. On the Takeout page with a leftover tab open (showing the CREATE A NEW EXPORT UI with "82 of 83 selected"), the page body contained text matching "in progress" — possibly from the Access Log Activity size notification or another page element. The pre-flight incorrectly halted the run. Fix: only match `'Export progress'` and `'Getting your files ready'` — strings that only appear on the actual active-export screen.

## Recommended Next Steps

1. **Wait before retrying** — Google's "please try again" is almost certainly rate-limiting from the repeated `Create export` clicks. Wait a few hours, then try a single clean run.
2. **Fix the history checkbox selector** — change `t.includes('watch history')` to `t.includes('history')` to match the actual modal label text.
3. **Add a screenshot before every click** to verify element visibility before firing CDP events.
4. **Single clean run sequence:**
   - Reload page (fresh state)
   - Wait 2s for full render
   - Deselect all (verify count = 0)
   - Check YouTube (verify count = 1)
   - Open data picker (verify modal open via screenshot)
   - Deselect all in modal
   - Select "history" (not "watch history")
   - OK
   - Next step
   - Create export (once, verify confirmation screen)
