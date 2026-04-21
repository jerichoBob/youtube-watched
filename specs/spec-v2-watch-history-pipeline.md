---
version: 2
name: watch-history-pipeline
display_name: "Watch History Processing Pipeline"
status: draft
created: 2026-04-20
depends_on: [1]
tags: [pipeline, transcripts, openai, summaries]
---

# Watch History Processing Pipeline

## Why (Problem Statement)

> As a user, I want to parse my Google Takeout watch history export and generate AI summaries of each video so that I can quickly review what I've been learning.

### Context

- Once the Takeout export (v1) delivers `watch-history.json`, this pipeline ingests it and enriches each entry
- `find-watched-videos.py` is the existing prototype — it has the right structure but uses browser-use for history fetching (now replaced by Takeout) and has a broken summarization path (old OpenAI API)
- `find-watched.py` is a simpler variant that only fetches URL + timestamp
- The Takeout JSON includes: video title, channel name, watch timestamp, video URL — no transcripts
- `youtube-transcript-api` can fetch transcripts for most videos without auth

---

## What (Requirements)

### Acceptance Criteria

- AC-1: Given a `watch-history.json` from Google Takeout, the pipeline produces a list of `VideoInfo` objects with title, channel, watch timestamp, and video ID
- AC-2: For each video, a transcript is fetched if available; description is used as fallback
- AC-3: With `--summarize`, each video gets a summary, key points, and learnings via OpenAI GPT-4o
- AC-4: Results saved to `youtube_summaries_YYYYMMDD.json`
- AC-5: `--days N` flag filters to videos watched in the last N days
- AC-6: `--start-date` / `--end-date` flags support explicit date ranges

### Out of Scope

- Re-fetching the Takeout export (v1)
- Search history, comments, or other YouTube data types

---

## How (Approach)

### Phase 1: Takeout JSON parser

- Write `parse_takeout.py` (or integrate into existing scripts) to load `watch-history.json`
- Map Takeout JSON fields to `VideoInfo` Pydantic model (title, channel, watch_date, video_url, video_id)
- Handle relative timestamps and timezone normalization
- Filter by date range

### Phase 2: Transcript fetching

- Reuse `get_video_transcript()` from `find-watched-videos.py`
- Extract video ID from URL reliably (handle `/watch?v=`, `/shorts/`, and `youtu.be/` formats)
- Gracefully skip videos with disabled transcripts

### Phase 3: AI summarization

- Update `generate_video_summary()` to use current OpenAI SDK (`openai>=1.0`)
- Use `gpt-4o` model (not deprecated `gpt-4`)
- Output: summary, key_points, learnings per video

### Phase 4: CLI wiring

- Single entry point: `process_history.py`
- Arguments: `--input` (path to watch-history.json), `--days`, `--start-date`, `--end-date`, `--summarize`
- Replaces `find-watched.py` and `find-watched-videos.py` as the canonical script

---

## Technical Notes

### Dependencies

- `youtube-transcript-api` — no auth required
- `openai>=1.0` — async client
- `pydantic` — VideoInfo, VideoInfoList models
- `python-dotenv` — `OPENAI_API_KEY` from `.env.local`

### Takeout JSON shape

```json
[
  {
    "header": "YouTube",
    "title": "Watched Some Video Title",
    "titleUrl": "https://www.youtube.com/watch?v=VIDEO_ID",
    "subtitles": [{"name": "Channel Name", "url": "..."}],
    "time": "2026-04-18T14:23:00.000Z",
    "products": ["YouTube"],
    "activityControls": ["YouTube watch history"]
  }
]
```

- Title includes "Watched " prefix — strip it
- `subtitles[0].name` is the channel name
- `time` is ISO 8601 UTC

### Risks & Mitigations

| Risk | Mitigation |
| ---- | ---------- |
| Transcript unavailable for many videos | Use description fallback; skip summarization if both empty |
| OpenAI rate limits on bulk summarization | Process sequentially with brief sleep between calls |

---

## Open Questions

1. Should summaries be cached so re-runs don't re-summarize already-processed videos?
2. What's the right output format for downstream use (JSON, markdown, both)?

---

## Changelog

| Date       | Change        |
| ---------- | ------------- |
| 2026-04-20 | Initial draft |
