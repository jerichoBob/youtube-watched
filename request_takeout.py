"""
Google Takeout - YouTube Watch History Export
==============================================
Pipe this to browser-harness to request a Takeout export containing
only your YouTube watch history:

    browser-harness < request_takeout.py

Requires:
  - browser-harness installed: cd ~/pgh/browser-harness && uv tool install -e .
  - Chrome with remote debugging enabled (one-time: chrome://inspect/#remote-debugging)
  - You must already be signed into Google in Chrome

Screenshots saved to /tmp/takeout-*.png at each step.
PATH output at the end is machine-readable for loop agents updating docs/takeout-loop-prompts.md.
"""

import json as _json

SHOTS = []
PATH  = []  # [{step, method, result, note}] — filled as we go

def snap(label):
    global SHOTS
    path = f"/tmp/takeout-{label}.png"
    screenshot(path)
    SHOTS.append(path)
    print(f"  📸 {path}")
    return path

def cdp_click(x, y):
    """Full CDP mouse event sequence — required for Material Design components."""
    cdp("Input.dispatchMouseEvent", type="mouseMoved",   x=x, y=y)
    cdp("Input.dispatchMouseEvent", type="mousePressed", x=x, y=y, button="left", clickCount=1)
    cdp("Input.dispatchMouseEvent", type="mouseReleased",x=x, y=y, button="left", clickCount=1)

def click_text(text_candidates, scope_js="document", scroll_to=None, step_name=""):
    """Find first visible element matching any candidate text and CDP click it. Records to PATH."""
    import json as _j  # exec() scoping: module-level imports not visible inside functions
    global PATH
    if scroll_to:
        js(f"{scroll_to}.scrollIntoView({{block:'center'}})")
        wait(0.5)
    # Inline find_pos to avoid exec() cross-function closure issue
    pos = None
    for _text in text_candidates:
        pos = js(f"""
        (function() {{
            const scope = {scope_js};
            const needle = {_j.dumps(_text)}.toLowerCase().trim();
            for (const el of scope.querySelectorAll('*')) {{
                const t = (el.innerText || '').trim().toLowerCase();
                if (t === needle) {{
                    const r = el.getBoundingClientRect();
                    if (r.width > 0 && r.height > 0 && r.top > -10 && r.top < window.innerHeight + 10)
                        return {{x: r.left + r.width/2, y: r.top + r.height/2, text: {_j.dumps(_text)}}};
                }}
            }}
            return null;
        }})()
        """)
        if pos:
            break
    if pos:
        cdp("Input.dispatchMouseEvent", type="mouseMoved",    x=pos['x'], y=pos['y'])
        cdp("Input.dispatchMouseEvent", type="mousePressed",  x=pos['x'], y=pos['y'], button="left", clickCount=1)
        cdp("Input.dispatchMouseEvent", type="mouseReleased", x=pos['x'], y=pos['y'], button="left", clickCount=1)
        print(f"  ✓ [{pos['text']}] at ({pos['x']:.0f}, {pos['y']:.0f})")
        PATH.append({"step": step_name, "method": "click_text+cdp", "text": pos['text'],
                     "pos": [round(pos['x']), round(pos['y'])], "result": "ok"})
        return pos
    PATH.append({"step": step_name, "method": "click_text+cdp", "candidates": text_candidates, "result": "not_found"})
    return None

def modal_scope():
    return "(document.querySelectorAll('[role=\"dialog\"]').length ? " \
           "[...document.querySelectorAll('[role=\"dialog\"]')].at(-1) : document)"

# ─────────────────────────────────────────────
# PRE-FLIGHT: check for in-progress export
# ─────────────────────────────────────────────
print("\n=== Google Takeout: YouTube Watch History Export ===\n")
print("Pre-flight: checking for in-progress export...")

# Pre-flight: detect a REAL in-progress export on an existing Takeout tab.
# "Getting your files ready" and "creating a copy of data" appear on the active export screen.
# "Export progress" is just a wizard step accordion label — never match it alone.
existing_tab = None
tabs = list_tabs(include_chrome=False)
for t in tabs:
    if 'takeout.google.com' in t.get('url', ''):
        existing_tab = t
        break

if existing_tab:
    switch_tab(existing_tab['targetId'])
    wait(1)
    matched = js("""
    (function() {
        const text = document.body.innerText;
        if (text.includes('Getting your files ready')) return 'Getting your files ready';
        if (text.includes('creating a copy of data')) return 'creating a copy of data';
        if (text.includes('You\\'ll receive an email when your export is done')) return 'export done email notice';
        return null;
    })()
    """)
    if matched:
        js("""
        (function() {
            const phrases = ['Getting your files ready', 'creating a copy of data', 'receive an email'];
            for (const el of document.querySelectorAll('*')) {
                const t = el.innerText || '';
                if (phrases.some(p => t.includes(p)) && el.children.length < 5) {
                    el.scrollIntoView({block: 'center'}); return;
                }
            }
        })()
        """)
        wait(0.5)
        snap("00-in-progress")
        print(f"  ⚠  An export is already in progress ('{matched}') — check the screenshot.")
        print("  Wait for it to complete and download before requesting a new one.")
        PATH.append({"step": "preflight", "result": "export_in_progress", "matched": matched})
        print("\nPATH:", _json.dumps(PATH, indent=2))
        raise SystemExit(0)
    print("  ✓ No export in progress on existing tab")
else:
    print("  ✓ No existing Takeout tab")

PATH.append({"step": "preflight", "result": "ok"})

# ─────────────────────────────────────────────
# STEP 1: Open Takeout
# ─────────────────────────────────────────────
print("\nStep 1: Opening Google Takeout...")
new_tab("https://takeout.google.com/settings/takeout")
wait_for_load()
wait(3)
snap("01-loaded")
info = page_info()
print(f"  URL: {info.get('url')}")

if "accounts.google.com" in info.get("url", ""):
    print("\n⚠  Chrome is not logged into Google. Sign in and re-run.")
    raise SystemExit(1)
if "takeout.google.com" not in info.get("url", ""):
    print(f"\n⚠  Unexpected URL: {info.get('url')}")
    raise SystemExit(1)

PATH.append({"step": "open_takeout", "result": "ok", "url": info.get("url")})
print("  ✓ Takeout page loaded")

# ─────────────────────────────────────────────
# STEP 2: Deselect all services
# ─────────────────────────────────────────────
print("\nStep 2: Deselecting all services...")
wait(2)

# Always scroll to top first — "Deselect all" is near the top of a very long page
js("window.scrollTo(0, 0)")
wait(1.5)

pos = click_text(["Deselect all"], step_name="deselect_all")
if not pos:
    snap("02-deselect-debug")
    print("  ⚠  Could not find 'Deselect all' — check screenshot")
else:
    wait(1.5)
    count = js("document.body.innerText.match(/\\d+ of \\d+ selected/)?.[0]")
    print(f"  Counter: {count}")
    if count and count.startswith("0"):
        PATH[-1]["verified"] = True
    snap("02-deselected")

# ─────────────────────────────────────────────
# STEP 3: Scroll to YouTube and check it
# ─────────────────────────────────────────────
print("\nStep 3: Enabling YouTube...")

# Scroll YouTube checkbox into view (instant, not smooth — smooth is async and position is stale)
js("""
(function() {
    const cb = document.querySelector('input[name="YouTube and YouTube Music"]');
    if (cb) cb.scrollIntoView({block: 'center'});
})()
""")
wait(1)  # wait for scroll to fully settle before capturing position

# Get checkbox position in a separate call AFTER scroll completes
cb_pos = js("""
(function() {
    const cb = document.querySelector('input[name="YouTube and YouTube Music"]');
    if (!cb) return null;
    const r = cb.getBoundingClientRect();
    if (r.width === 0 || r.top < 0 || r.top > window.innerHeight) return null;
    return {x: r.left + r.width/2, y: r.top + r.height/2};
})()
""")

if cb_pos:
    cdp_click(cb_pos['x'], cb_pos['y'])
    wait(1)
    checked = js('document.querySelector(\'input[name="YouTube and YouTube Music"]\').checked')
    count = js("document.body.innerText.match(/\\d+ of \\d+ selected/)?.[0]")
    print(f"  ✓ YouTube checked={checked}, counter={count}")
    PATH.append({"step": "check_youtube", "method": "cdp_click_on_input", "result": "ok" if checked else "click_failed",
                 "checked": checked, "counter": count})
else:
    print("  ⚠  YouTube checkbox not found")
    PATH.append({"step": "check_youtube", "result": "not_found"})

snap("03-youtube-checked")

# ─────────────────────────────────────────────
# STEP 4: Open YouTube data options
# ─────────────────────────────────────────────
print("\nStep 4: Opening YouTube data options...")

# The button innerText is "list\nN type(s) selected" or "list\nAll YouTube data included"
btn_pos = js("""
(function() {
    for (const el of document.querySelectorAll('button, [role="button"], a')) {
        const t = (el.innerText || el.textContent || '').trim();
        if (t.includes('type selected') || t.includes('YouTube data included') || t.includes('All data included')) {
            el.scrollIntoView({block: 'center'});
            const r = el.getBoundingClientRect();
            if (r.width > 0) return {x: r.left + r.width/2, y: r.top + r.height/2, text: t.replace(/\\n/g,' ').slice(0,50)};
        }
    }
    return null;
})()
""")
wait(0.5)

if btn_pos:
    cdp_click(btn_pos['x'], btn_pos['y'])
    print(f"  ✓ Opened: '{btn_pos['text']}'")
    PATH.append({"step": "open_data_options", "method": "cdp_click", "text": btn_pos['text'], "result": "ok"})
else:
    snap("04-options-debug")
    print("  ⚠  Options button not found")
    PATH.append({"step": "open_data_options", "result": "not_found"})

wait(2)
snap("04-modal")

# ─────────────────────────────────────────────
# STEP 5: In modal — deselect all, select history
# ─────────────────────────────────────────────
print("\nStep 5: Selecting only watch history...")

# Deselect all inside modal
modal = modal_scope()
desel_pos = js(f"""
(function() {{
    const scope = {modal};
    for (const el of scope.querySelectorAll('*')) {{
        if ((el.innerText || '').trim().toLowerCase() === 'deselect all') {{
            const r = el.getBoundingClientRect();
            if (r.width > 0) return {{x: r.left + r.width/2, y: r.top + r.height/2}};
        }}
    }}
    return null;
}})()
""")
if desel_pos:
    cdp_click(desel_pos['x'], desel_pos['y'])
    print("  ✓ Deselected all in modal")
    wait(0.5)
else:
    print("  ⚠  Modal 'Deselect all' not found")

# Select history — find the text "history" in the modal, then get its associated checkbox.
# Modal uses div/span structure (not li/label), so text lives in a sibling span.
# Strategy: find the text node, walk up to the row container, find checkbox inside it.
history_pos = js(f"""
(function() {{
    const scope = {modal};
    // Find the element whose sole text content is "history"
    for (const el of scope.querySelectorAll('*')) {{
        const t = (el.innerText || '').trim().toLowerCase();
        if (t === 'history' && el.children.length === 0) {{
            // Walk up to find the row container that also contains a checkbox
            let row = el.parentElement;
            for (let i = 0; i < 4 && row; i++) {{
                const cb = row.querySelector('input[type="checkbox"]');
                if (cb) {{
                    cb.scrollIntoView({{block: 'center'}});
                    const r = cb.getBoundingClientRect();
                    if (r.width > 0) return {{x: r.left + r.width/2, y: r.top + r.height/2, label: 'history'}};
                }}
                row = row.parentElement;
            }}
        }}
    }}
    return null;
}})()
""")

if history_pos:
    cdp_click(history_pos['x'], history_pos['y'])
    print(f"  ✓ Selected: '{history_pos['label']}'")
    PATH.append({"step": "select_history", "method": "cdp_click", "label": history_pos['label'], "result": "ok"})
else:
    snap("05-history-debug")
    print("  ⚠  History checkbox not found — check screenshot")
    PATH.append({"step": "select_history", "result": "not_found"})

wait(0.5)
snap("05-history-selected")

# ─────────────────────────────────────────────
# STEP 6: OK to close modal
# ─────────────────────────────────────────────
print("\nStep 6: Confirming selection (OK)...")
ok_pos = js(f"""
(function() {{
    const scope = {modal};
    for (const el of scope.querySelectorAll('button, [role="button"]')) {{
        const t = (el.innerText || '').trim().toLowerCase();
        if (t === 'ok' || t === 'done') {{
            const r = el.getBoundingClientRect();
            return {{x: r.left + r.width/2, y: r.top + r.height/2, text: t}};
        }}
    }}
    return null;
}})()
""")
if ok_pos:
    cdp_click(ok_pos['x'], ok_pos['y'])
    print(f"  ✓ Clicked '{ok_pos['text']}'")
    PATH.append({"step": "ok_modal", "result": "ok"})
else:
    snap("06-ok-debug")
    print("  ⚠  OK button not found")
    PATH.append({"step": "ok_modal", "result": "not_found"})

wait(2)
snap("06-confirmed")
count = js("document.body.innerText.match(/\\d+ of \\d+ selected/)?.[0]")
print(f"  Counter after OK: {count}")

# ─────────────────────────────────────────────
# STEP 7: Next step
# ─────────────────────────────────────────────
print("\nStep 7: Next step...")
js("window.scrollTo(0, document.body.scrollHeight)")
wait(1)

next_pos = js("""
(function() {
    for (const el of document.querySelectorAll('button, [role="button"]')) {
        if ((el.innerText || '').trim().toLowerCase() === 'next step') {
            const r = el.getBoundingClientRect();
            return {x: r.left + r.width/2, y: r.top + r.height/2};
        }
    }
    return null;
})()
""")
if next_pos:
    cdp_click(next_pos['x'], next_pos['y'])
    print("  ✓ Clicked 'Next step'")
    PATH.append({"step": "next_step", "result": "ok"})
else:
    snap("07-nextstep-debug")
    print("  ⚠  'Next step' not found")
    PATH.append({"step": "next_step", "result": "not_found"})

wait(3)
snap("07-step2")

# ─────────────────────────────────────────────
# STEP 8: Create export
# ─────────────────────────────────────────────
print("\nStep 8: Create export...")
wait_for_load()
wait(2)
js("window.scrollTo(0, document.body.scrollHeight)")
wait(1)

create_pos = js("""
(function() {
    for (const el of document.querySelectorAll('button, [role="button"]')) {
        if ((el.innerText || '').trim().toLowerCase() === 'create export') {
            el.scrollIntoView({block: 'center'});
            const r = el.getBoundingClientRect();
            return {x: r.left + r.width/2, y: r.top + r.height/2};
        }
    }
    return null;
})()
""")
snap("08-before-create")

if create_pos:
    cdp_click(create_pos['x'], create_pos['y'])
    print("  ✓ Clicked 'Create export'")
    wait(4)
    snap("08-final")

    final_text = js("document.body.innerText")
    if "please try" in final_text.lower():
        outcome = "rate_limited"
        print("  ⚠  Rate limited — 'Please try to create your export again'")
    elif ("getting your files" in final_text.lower() or
          "receive an email" in final_text.lower() or
          "creating a copy of data" in final_text.lower() or
          "your export has been created" in final_text.lower()):
        outcome = "success"
        print("  ✓ Export confirmed!")
    else:
        outcome = "unknown"
        print("  ? Unknown outcome — check screenshot 08-final.png")

    PATH.append({"step": "create_export", "result": outcome})
else:
    print("  ⚠  'Create export' button not found")
    PATH.append({"step": "create_export", "result": "button_not_found"})
    outcome = "button_not_found"

# ─────────────────────────────────────────────
# SUMMARY
# ─────────────────────────────────────────────
print("\n=== Summary ===")
print(f"Outcome: {outcome}")
print("Screenshots:")
for s in SHOTS:
    print(f"  {s}")

print("\n--- PATH (machine-readable for loop agent) ---")
print(_json.dumps(PATH, indent=2))
print("--- END PATH ---")
