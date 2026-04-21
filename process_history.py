"""
Watch History Pipeline
======================
Parses a Google Takeout watch-history.html, optionally fetches transcripts,
and optionally generates AI summaries via OpenAI gpt-4o.

Usage:
    python process_history.py --input PATH/watch-history.html
    python process_history.py --input PATH/watch-history.html --days 7
    python process_history.py --input PATH/watch-history.html --days 7 --summarize
    python process_history.py --input PATH/watch-history.html --start-date 2026-04-01 --end-date 2026-04-21
"""

import argparse
import html as _html
import json
import re
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv(".env.local")

# ─────────────────────────────────────────────
# Models
# ─────────────────────────────────────────────

class VideoInfo(BaseModel):
    title: str
    channel: str
    watch_date: datetime
    video_url: str
    video_id: Optional[str] = None
    transcript: Optional[str] = None
    summary: Optional[str] = None
    key_points: list[str] = []
    learnings: list[str] = []


# ─────────────────────────────────────────────
# Parsing
# ─────────────────────────────────────────────

# Non-breaking space (\xa0) follows "Watched" in Takeout HTML.
# Narrow no-break space ( ) appears between time and AM/PM.
_ENTRY_RE = re.compile(
    r'Watched[\xa0\s]<a href="([^"]+)">([^<]+)</a>'
    r'<br><a href="([^"]+)">([^<]+)</a>'
    r'<br>([^<]+)<br>'
)

_MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


def _parse_timestamp(raw: str) -> Optional[datetime]:
    """Parse Takeout date strings like 'Apr 21, 2026, 8:02:27 AM EDT'."""
    # Normalize unicode spaces and strip
    s = raw.replace(" ", " ").replace("\xa0", " ").strip()
    # Drop timezone abbreviation (EDT, PDT, etc.) — treat as local, then store as-is
    s = re.sub(r'\s+[A-Z]{2,4}$', '', s)
    for fmt in ("%b %d, %Y, %I:%M:%S %p", "%b %d, %Y, %I:%M %p"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            pass
    return None


def _extract_video_id(url: str) -> Optional[str]:
    """Extract video ID from /watch?v=, /shorts/, or youtu.be/ URLs."""
    m = re.search(r'[?&]v=([A-Za-z0-9_-]{11})', url)
    if m:
        return m.group(1)
    m = re.search(r'/shorts/([A-Za-z0-9_-]{11})', url)
    if m:
        return m.group(1)
    m = re.search(r'youtu\.be/([A-Za-z0-9_-]{11})', url)
    if m:
        return m.group(1)
    return None


def parse_watch_history(html_path: Path) -> list[VideoInfo]:
    content = html_path.read_text(encoding="utf-8")
    videos = []
    for m in _ENTRY_RE.finditer(content):
        video_url, title, _channel_url, channel, timestamp_raw = m.groups()
        watch_date = _parse_timestamp(timestamp_raw)
        if watch_date is None:
            continue  # skip malformed entries (YouTube TV live content has different structure)
        videos.append(VideoInfo(
            title=_html.unescape(title),
            channel=_html.unescape(channel),
            watch_date=watch_date,
            video_url=video_url,
            video_id=_extract_video_id(video_url),
        ))
    return videos


def filter_by_date(videos: list[VideoInfo], start: Optional[datetime], end: Optional[datetime]) -> list[VideoInfo]:
    if start is None and end is None:
        return videos
    result = []
    for v in videos:
        if start and v.watch_date < start:
            continue
        if end and v.watch_date > end:
            continue
        result.append(v)
    return result


# ─────────────────────────────────────────────
# Transcripts
# ─────────────────────────────────────────────

def fetch_transcript(video_id: str, video_url: str) -> Optional[str]:
    """Fetch transcript via yt-dlp (handles auth, cookies, and format negotiation)."""
    try:
        import yt_dlp
        opts = {
            "skip_download": True,
            "writesubtitles": True,
            "writeautomaticsub": True,
            "subtitleslangs": ["en", "en-US"],
            "quiet": True,
            "no_warnings": True,
        }
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(video_url, download=False)

        # Pull subtitles out of the info dict (manual first, then auto-generated)
        subs = info.get("subtitles", {}) or {}
        auto = info.get("automatic_captions", {}) or {}
        tracks = (
            subs.get("en") or subs.get("en-US") or
            auto.get("en") or auto.get("en-US") or []
        )
        if not tracks:
            return None

        # Prefer json3 format; fall back to whatever is available
        track = next((t for t in tracks if t.get("ext") == "json3"), tracks[0])

        import urllib.request
        with urllib.request.urlopen(track["url"]) as resp:
            raw = resp.read().decode("utf-8")

        if track.get("ext") == "json3":
            data = json.loads(raw)
            parts = []
            for event in data.get("events", []):
                for seg in event.get("segs", []):
                    t = seg.get("utf8", "").strip()
                    if t and t != "\n":
                        parts.append(t)
            return _html.unescape(" ".join(parts)) if parts else None
        else:
            # Strip XML/VTT tags and return plain text
            text = re.sub(r"<[^>]+>", " ", raw)
            text = re.sub(r"\s+", " ", text).strip()
            return _html.unescape(text) if text else None

    except Exception:
        return None


# ─────────────────────────────────────────────
# Summarization
# ─────────────────────────────────────────────

def summarize_video(video: VideoInfo, client) -> VideoInfo:
    content = video.transcript or f"Title: {video.title}\nChannel: {video.channel}"
    prompt = f"""Summarize this YouTube video for someone who watched it and wants a quick review.

Title: {video.title}
Channel: {video.channel}

Transcript (or description):
{content[:8000]}

Respond with JSON only:
{{
  "summary": "2-3 sentence summary",
  "key_points": ["point 1", "point 2", "point 3"],
  "learnings": ["learning 1", "learning 2"]
}}"""

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
    )
    data = json.loads(response.choices[0].message.content)
    return video.model_copy(update={
        "summary": data.get("summary", ""),
        "key_points": data.get("key_points", []),
        "learnings": data.get("learnings", []),
    })


# ─────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Process YouTube watch history from Google Takeout")
    parser.add_argument("--input", required=True, help="Path to watch-history.html")
    parser.add_argument("--days", type=int, help="Only include videos watched in the last N days")
    parser.add_argument("--start-date", help="Start date YYYY-MM-DD (inclusive)")
    parser.add_argument("--end-date", help="End date YYYY-MM-DD (inclusive)")
    parser.add_argument("--summarize", action="store_true", help="Fetch transcripts and generate AI summaries")
    parser.add_argument("--limit", type=int, help="Only process the first N videos (useful for testing)")
    parser.add_argument("--output", help="Output JSON path (default: youtube_summaries_YYYYMMDD.json)")
    args = parser.parse_args()

    html_path = Path(args.input)
    if not html_path.exists():
        print(f"File not found: {html_path}", file=sys.stderr)
        sys.exit(1)

    # Date range
    now = datetime.now()
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None

    if args.days:
        start_date = now - timedelta(days=args.days)
    if args.start_date:
        start_date = datetime.strptime(args.start_date, "%Y-%m-%d")
    if args.end_date:
        end_date = datetime.strptime(args.end_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59)

    print(f"Parsing {html_path}...")
    videos = parse_watch_history(html_path)
    print(f"  Total entries: {len(videos)}")

    videos = filter_by_date(videos, start_date, end_date)
    print(f"  After date filter: {len(videos)}")

    if not videos:
        print("No videos match the date range.")
        sys.exit(0)

    if args.limit:
        videos = videos[:args.limit]
        print(f"  Limited to first {len(videos)} videos")

    if args.summarize:
        import os
        import time
        from openai import OpenAI

        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            print("OPENAI_API_KEY not set in .env.local", file=sys.stderr)
            sys.exit(1)
        client = OpenAI(api_key=api_key)

        print(f"\nFetching transcripts and summaries for {len(videos)} videos...")
        for i, video in enumerate(videos):
            print(f"  [{i+1}/{len(videos)}] {video.title[:60]}")
            if video.video_id:
                transcript = fetch_transcript(video.video_id, video.video_url)
                if transcript:
                    videos[i] = videos[i].model_copy(update={"transcript": transcript})
                    print(f"    transcript: {len(transcript)} chars")
                else:
                    print(f"    transcript: unavailable")
            try:
                videos[i] = summarize_video(videos[i], client)
                print(f"    summary: ok")
            except Exception as e:
                print(f"    summary: failed — {e}", file=sys.stderr)
            if i < len(videos) - 1:
                time.sleep(0.5)

    output_path = args.output or f"youtube_summaries_{now.strftime('%Y%m%d')}.json"
    output = [v.model_dump(mode="json") for v in videos]
    Path(output_path).write_text(json.dumps(output, indent=2, default=str))
    print(f"\nSaved {len(videos)} entries to {output_path}")


if __name__ == "__main__":
    main()
