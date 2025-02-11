import os
import datetime
from typing import List, Optional

import openai
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

# The youtube_transcript_api package can be installed via: pip install youtube-transcript-api
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound

# -----------------------------------------------------------------------------------
# 1. Define Pydantic Models for Structured Data
# -----------------------------------------------------------------------------------

class VideoSummaryRequest(BaseModel):
    video_id: str
    title: str
    transcript: str

class VideoSummaryResponse(BaseModel):
    video_id: str
    summary: str

class VideoInfo(BaseModel):
    video_id: str
    title: str
    watch_date: datetime.datetime
    description: Optional[str] = ""  # Fallback if transcript is unavailable

# -----------------------------------------------------------------------------------
# 2. Function to Retrieve (or Simulate) YouTube Watch History
# -----------------------------------------------------------------------------------

def get_dummy_watch_history() -> List[VideoInfo]:
    """
    Simulate retrieval of watch history.
    Replace this function with actual YouTube API calls (with OAuth2) or
    your own method of accessing YouTube history.
    """
    now = datetime.datetime.now()
    one_day = datetime.timedelta(days=1)
    videos = [
        VideoInfo(
            video_id="abc123",
            title="Understanding Quantum Entanglement",
            watch_date=now - one_day,  # Watched 1 day ago
            description="A deep dive into the quantum phenomenon of entanglement..."
        ),
        VideoInfo(
            video_id="def456",
            title="Advances in AI: Transformers Explained",
            watch_date=now - one_day * 3,  # Watched 3 days ago
            description="An overview of the latest advancements in AI focusing on transformers..."
        )
        # Add more dummy videos as needed.
    ]
    return videos

# -----------------------------------------------------------------------------------
# 3. Function to Get Video Transcript via youtube_transcript_api
# -----------------------------------------------------------------------------------

def get_video_transcript(video_id: str) -> Optional[str]:
    """
    Attempts to retrieve the transcript of a given YouTube video.
    Returns the transcript as a single string if available, or None otherwise.
    """
    try:
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
        transcript = " ".join([segment["text"] for segment in transcript_list])
        return transcript
    except (TranscriptsDisabled, NoTranscriptFound):
        # Transcript is not available
        return None
    except Exception as e:
        print(f"Error retrieving transcript for video {video_id}: {e}")
        return None

# -----------------------------------------------------------------------------------
# 4. Function to Generate a High-Level Summary Using OpenAI's ChatCompletion API
# -----------------------------------------------------------------------------------

def generate_video_summary(request: VideoSummaryRequest) -> VideoSummaryResponse:
    """
    Uses OpenAI's ChatCompletion API to generate a summary.
    The prompt includes the video's title and content (transcript or description).
    """
    prompt = (
        f"Provide a concise high-level summary for the following YouTube video content. "
        f"The video is titled '{request.title}'.\n\nContent:\n{request.transcript}\n\nSummary:"
    )
    try:
        client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful assistant that summarizes technical YouTube videos."
                },
                {"role": "user", "content": prompt}
            ],
            temperature=0.5,
        )
        summary = response.choices[0].message.content.strip()
        return VideoSummaryResponse(video_id=request.video_id, summary=summary)
    except Exception as e:
        print(f"Error generating summary for video {request.video_id}: {e}")
        return VideoSummaryResponse(video_id=request.video_id, summary="Summary generation failed.")

# -----------------------------------------------------------------------------------
# 5. Main Application Logic
# -----------------------------------------------------------------------------------

def main():
    # 5.1. Set your OpenAI API key (ensure you've set the OPENAI_API_KEY environment variable)
    openai.api_key = os.environ.get("OPENAI_API_KEY")
    if openai.api_key is None:
        print("Please set your OPENAI_API_KEY environment variable.")
        return

    # 5.2. Retrieve the list of watched videos (using dummy data for demonstration)
    videos = get_dummy_watch_history()

    # 5.3. Filter videos watched within the past week
    one_week_ago = datetime.datetime.now() - datetime.timedelta(weeks=1)
    recent_videos = [video for video in videos if video.watch_date >= one_week_ago]

    # 5.4. For each recent video, retrieve transcript (or fallback to description) and generate summary
    summaries = []
    for video in recent_videos:
        print(f"Processing video: {video.title}")
        transcript = get_video_transcript(video.video_id)
        if transcript is None:
            # Fallback: use the video description if no transcript is available
            transcript = video.description
        if not transcript:
            print(f"No transcript or description available for video: {video.video_id}. Skipping.")
            continue

        summary_request = VideoSummaryRequest(
            video_id=video.video_id,
            title=video.title,
            transcript=transcript
        )
        summary_response = generate_video_summary(summary_request)
        summaries.append(summary_response)

    # 5.5. Output the summaries in a numbered list format
    print("\nSummary of videos watched in the past week:")
    for idx, summary in enumerate(summaries, start=1):
        print(f"{idx}. Video ID: {summary.video_id}")
        print(f"   Summary: {summary.summary}\n")

if __name__ == '__main__':
    main()