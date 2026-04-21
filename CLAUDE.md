# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Does

Fetches YouTube watch history by having an AI agent (browser-use) log into `myactivity.google.com`, scrape watch history with infinite scroll, then optionally fetches video transcripts via `youtube-transcript-api` and generates AI summaries via OpenAI GPT-4.

## Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
playwright install
```

Credentials go in `.env.local` (already gitignored via `.env.*`):
```
OPENAI_API_KEY=...
GOOGLE_USERNAME=...
GOOGLE_PASSWORD=...
```

## Running

```bash
# Simpler history-only scraper
python find-watched.py --days 7

# Full pipeline with Pydantic models + optional summarization
python find-watched-videos.py --days 2
python find-watched-videos.py --days 2 --summarize
```

Output is saved to `data/watched_<start>-<end>.json` (for `find-watched.py`) or `video_info.json` / `youtube_summaries_YYYYMMDD.json` (for `find-watched-videos.py`). The `data/` directory is gitignored.

## Architecture

### Two parallel scripts

**`find-watched.py`** — minimal version. Fetches only `video_url` + `watch_timestamp`. Saves to `data/` directory. Uses `Credentials` Pydantic model with `SecretStr` for secure credential handling.

**`find-watched-videos.py`** — full pipeline. Has richer Pydantic models (`VideoInfo`, `VideoInfoList`, `VideoSummaryRequest/Response`) that include title, author, description, and transcript. Also contains the summarization pipeline via OpenAI.

### Core pattern: browser-use agent + custom actions

`browser_use.Agent` takes a natural-language task and a `ChatOpenAI` LLM, then drives a real Chromium browser. Custom actions are registered on a `Controller` instance with the `@controller.action` decorator and passed to `Agent(controller=controller)`. The `save_video_info` action in `find-watched-videos.py` is how the agent writes structured data to disk during execution.

Credentials are passed to the agent via `sensitive_data={}` — browser-use redacts these from logs.

### 2FA handling

The agent is instructed to print `2FA_REQUIRED` if it detects a 2FA prompt. The main loop checks for this and calls `wait_for_user_2fa()` which blocks on `input()` until the user completes it in the browser window.

### `hackernews-test.py` / `save-file-action.py`

Standalone experiments for browser-use features (output validator, custom actions). Not part of the main pipeline.

## Key Dependencies

- `browser-use` + `playwright` — AI-controlled browser automation
- `langchain-openai` — LLM wrapper required by browser-use
- `youtube-transcript-api` — transcript fetching (no auth needed)
- `python-dotenv` — loads `.env.local`
- `pydantic` — data models throughout
