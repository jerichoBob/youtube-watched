# Specs — youtube-watched

> Single source of truth for all specifications. Parsed by `specs-parse.sh`.

---

## Quick Status

| Spec | Name | Progress | Status | Owner |
| ---- | ---- | -------- | ------ | ----- |
| v1 | Google Takeout Automation | 0/7 | ✏️ Draft | robert.w.seaton.jr@gmail.com |
| v2 | Watch History Processing Pipeline | 0/8 | ✏️ Draft | robert.w.seaton.jr@gmail.com |
| v3 | Loop-Based Automation Optimization | 0/6 | ✏️ Draft | robert.w.seaton.jr@gmail.com |

---

## v1: Google Takeout Automation

**Spec**: [spec-v1-takeout-automation.md](spec-v1-takeout-automation.md)

### Phase 1: Fix known bugs in request_takeout.py

- [ ] Fix history checkbox selector (`'watch history'` → `'history'`)
- [ ] Add scroll-to-top + 2s wait guard before "Deselect all"
- [ ] Fix exec() closure issue (flatten helpers, use `global` for mutable state)

### Phase 2: Validate clean run sequence

- [ ] Verify each step gate (0 of 83, 1 of 83, modal open, history checked, step 2 expanded)
- [ ] Confirm export screen with no error message

### Phase 3: Harden and document

- [ ] Add pre-flight check for in-progress export
- [ ] Update `docs/takeout-loop-prompts.md` with actual path and outcome

---

## v2: Watch History Processing Pipeline

**Spec**: [spec-v2-watch-history-pipeline.md](spec-v2-watch-history-pipeline.md)

### Phase 1: Takeout JSON parser

- [ ] Parse `watch-history.json` into `VideoInfo` Pydantic models
- [ ] Filter by date range (`--days`, `--start-date`, `--end-date`)

### Phase 2: Transcript fetching

- [ ] Extract video ID from all URL formats
- [ ] Fetch transcripts via `youtube-transcript-api`, skip gracefully if unavailable

### Phase 3: AI summarization

- [ ] Update summarization to current OpenAI SDK and `gpt-4o`
- [ ] Output: summary, key_points, learnings per video

### Phase 4: CLI wiring

- [ ] Single `process_history.py` entry point replacing `find-watched.py` / `find-watched-videos.py`
- [ ] Save results to `youtube_summaries_YYYYMMDD.json`

---

## v3: Loop-Based Automation Optimization

**Spec**: [spec-v3-loop-optimization.md](spec-v3-loop-optimization.md)

### Phase 1: Establish baseline prompt

- [ ] Run v1 loop prompt; record actual path and outcome in `docs/takeout-loop-prompts.md`

### Phase 2: Iterate toward convergence

- [ ] Fix bugs discovered by loop; increment prompt version each time
- [ ] Stop when actual path matches expected on two consecutive runs

### Phase 3: Canonicalize

- [ ] Write final stable prompt as canonical version in `docs/takeout-loop-prompts.md`
- [ ] Confirm `request_takeout.py` reflects all fixes
- [ ] Update `CLAUDE.md` run instructions

---

## Architecture

The project has three distinct stages that feed into each other:

1. **Takeout request** (`request_takeout.py`) — browser-harness automation to kick off a Google Takeout export
2. **History processing** (`process_history.py`) — parse the resulting JSON, fetch transcripts, generate summaries
3. **Loop optimization** — iterative self-improvement of stage 1 via `/loop` until the automation is reliable

Credentials live in `.env.local` (gitignored). All browser automation uses the user's existing Chrome session via CDP — no credential automation.
