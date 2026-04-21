# YouTube Watch History Summarizer

Fetches your YouTube watch history by automating a browser session against `myactivity.google.com`, then optionally retrieves video transcripts and generates AI-powered summaries.

## Setup

```shell
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
playwright install
```

Create a `.env.local` file with your credentials:
```
OPENAI_API_KEY=your_openai_api_key
GOOGLE_USERNAME=your_google_email
GOOGLE_PASSWORD=your_google_password
```

## Usage

```bash
# Fetch history for the last N days (URL + timestamp only)
python find-watched.py --days 7

# Fetch history with titles/authors/transcripts, optionally summarize
python find-watched-videos.py --days 2
python find-watched-videos.py --days 2 --summarize

# Specify an explicit date range
python find-watched.py --start-date 2024-02-01 --end-date 2024-02-15
```

On first run a browser window will open for Google login. If 2FA is required, complete it in the browser and press Enter in the terminal when done.

Output:
- `find-watched.py` → `data/watched_<start>-<end>.json`
- `find-watched-videos.py` → `video_info.json` and (with `--summarize`) `youtube_summaries_YYYYMMDD.json`

## Notes

- Watch history is scraped from `myactivity.google.com` via an AI-controlled browser; no YouTube Data API key is required
- Video transcripts are retrieved when available via `youtube-transcript-api`; summaries fall back to video descriptions
- Summaries are generated using OpenAI GPT-4