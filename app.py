import os
os.environ["ANONYMIZED_TELEMETRY"] = "false"

import json
from typing import List, Optional
from datetime import datetime, timedelta, timezone
from dateutil import parser

import openai
from pydantic import BaseModel, SecretStr
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from browser_use import Agent
import asyncio

# Load environment variables from .env.local first, then fall back to .env
load_dotenv('.env.local')
load_dotenv()

from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound

# -----------------------------------------------------------------------------------
# 1. Define Pydantic Models for Structured Data
# -----------------------------------------------------------------------------------

class VideoSummaryRequest(BaseModel):
    video_id: str
    title: str
    transcript: str
    description: Optional[str] = ""
    author: str

class VideoSummaryResponse(BaseModel):
    video_id: str
    title: str
    author: str
    watch_date: datetime
    summary: str
    key_points: List[str]
    learnings: List[str]

class VideoInfo(BaseModel):
    video_id: str
    title: str
    author: str
    watch_date: datetime
    description: Optional[str] = ""

# -----------------------------------------------------------------------------------
# 2. Function to Get Watch History using browser-use
# -----------------------------------------------------------------------------------

async def wait_for_user_2fa():
    """
    Prompt user to complete 2FA and wait for their confirmation.
    """
    print("\n2FA detected! Please complete the authentication in the browser.")
    print("After completing 2FA, press Enter to continue...")
    input()
    print("Continuing with watch history fetch...")

def get_google_credentials():
    """Get Google credentials from environment variables."""
    username = os.getenv('GOOGLE_USERNAME')
    password = os.getenv('GOOGLE_PASSWORD')
    
    if not username or not password:
        raise ValueError("GOOGLE_USERNAME and GOOGLE_PASSWORD must be set in .env.local")
    
    return username, password

async def get_watch_history(days: int = 7) -> List[VideoInfo]:
    """
    Retrieve watch history using browser-use to access YouTube directly.
    """
    print("\nFetching watch history from the past 7 days...")
    threshold_date = datetime.now(timezone.utc) - timedelta(days=days)
    
    # Get credentials from environment
    un, pw = get_google_credentials()
    
    # Create a task for the browser agent with credentials
    task = f"""
    1. Go to https://accounts.google.com/signin
    2. Find the email/username input field and the google_username
    3. Click next or continue
    4. Find the password input field and enter: google_password
    5. Check if there's a 2FA screen (look for elements mentioning "2-Step Verification" or showing a phone icon)
    6. If 2FA is detected:
       - Print "2FA_REQUIRED" to the console
       - Wait for further instructions before proceeding
    7. After successful login (or after 2FA completion), go to https://www.youtube.com/feed/history
    8. Wait for the page to load completely
    9. For each video in the history:
       - Extract the video title
       - Extract the channel name (author)
       - Extract the watch date
       - Extract the video URL
       - Extract any available description
    10. Only include videos watched after {threshold_date.isoformat()}
    11. Return the data as a JSON array with objects containing:
       - title
       - author
       - watch_date
       - video_id (extracted from URL)
       - description
    """
    
    try:
        # Create and run the agent
        agent = Agent(
            task=task,
            llm=ChatOpenAI(model="gpt-4o"),
            sensitive_data = {'google_username': un, 'google_password': pw}
        )
        
        # Start the agent
        result = await agent.run()
        
        # Check if we need to handle 2FA
        if isinstance(result, str) and "2FA_REQUIRED" in result:
            await wait_for_user_2fa()
            # After 2FA is completed, continue with the history fetch
            result = await agent.run()
        
        # Parse the result (assuming it's a JSON string)
        videos_data = json.loads(result)
        
        # Convert the data into VideoInfo objects
        videos = []
        for video in videos_data:
            try:
                # Extract video ID from URL if needed
                video_id = video.get('video_id')
                if not video_id and 'url' in video:
                    # Extract ID from URL like https://www.youtube.com/watch?v=VIDEO_ID
                    video_id = video['url'].split('v=')[-1].split('&')[0]
                
                # Parse the watch date
                watch_date = parser.parse(video['watch_date']).replace(tzinfo=timezone.utc)
                
                # Create VideoInfo object
                video_info = VideoInfo(
                    video_id=video_id,
                    title=video['title'],
                    author=video['author'],
                    watch_date=watch_date,
                    description=video.get('description', '')
                )
                videos.append(video_info)
                print(f"Added video: {video_info.title}")
            except Exception as e:
                print(f"Error processing video data: {str(e)}")
                continue
        
        return videos
        
    except Exception as e:
        print(f"Error fetching watch history: {str(e)}")
        print("\nFull error traceback:")
        import traceback
        print(traceback.format_exc())
        return []

# -----------------------------------------------------------------------------------
# 3. Function to Get Video Transcript
# -----------------------------------------------------------------------------------

def get_video_transcript(video_id: str) -> Optional[str]:
    """
    Attempts to retrieve the transcript of a given YouTube video.
    Returns the transcript as a single string if available, or None otherwise.
    """
    try:
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
        return ' '.join(item['text'] for item in transcript_list)
    except (TranscriptsDisabled, NoTranscriptFound):
        return None
    except Exception as e:
        print(f"Error getting transcript for video {video_id}: {str(e)}")
        return None

# -----------------------------------------------------------------------------------
# 4. Function to Generate Video Summary Using OpenAI's ChatCompletion API
# -----------------------------------------------------------------------------------

async def generate_video_summary(request: VideoSummaryRequest) -> VideoSummaryResponse:
    """
    Uses OpenAI's ChatCompletion API to generate a comprehensive summary.
    """
    openai.api_key = os.getenv('OPENAI_API_KEY')
    
    prompt = f"""
    Title: {request.title}
    Author: {request.author}
    
    Content:
    {request.transcript if request.transcript else request.description}
    
    Please provide:
    1. A concise summary of the video
    2. Key points discussed (as a list)
    3. Main things someone would learn from this video (as a list)
    
    Format the response in JSON with these keys: summary, key_points, learnings
    """
    
    try:
        response = await openai.ChatCompletion.acreate(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a helpful AI that creates concise video summaries."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7
        )
        
        result = json.loads(response.choices[0].message.content)
        return VideoSummaryResponse(
            video_id=request.video_id,
            title=request.title,
            author=request.author,
            watch_date=datetime.now(timezone.utc),
            summary=result["summary"],
            key_points=result["key_points"],
            learnings=result["learnings"]
        )
    except json.JSONDecodeError:
        # Fallback if the response isn't proper JSON
        content = response.choices[0].message.content
        return VideoSummaryResponse(
            video_id=request.video_id,
            title=request.title,
            author=request.author,
            watch_date=datetime.now(timezone.utc),
            summary=content,
            key_points=[],
            learnings=[]
        )

# -----------------------------------------------------------------------------------
# 5. Main Application Logic
# -----------------------------------------------------------------------------------

async def main():
    # Get watch history for the past week
    videos = await get_watch_history(days=7)
    
    if not videos:
        print("No videos found in your watch history for the past week.")
        return
    
    print(f"\nFound {len(videos)} videos in your watch history:\n")
    
    # Sort videos by watch date, newest first
    videos.sort(key=lambda x: x.watch_date, reverse=True)
    
    # Process each video
    summaries = []
    for video in videos:
        print(f"\nProcessing video: {video.title}")
        
        # Get transcript
        transcript = get_video_transcript(video.video_id)
        
        # Generate summary
        summary_request = VideoSummaryRequest(
            video_id=video.video_id,
            title=video.title,
            transcript=transcript if transcript else "",
            description=video.description,
            author=video.author
        )
        
        summary = await generate_video_summary(summary_request)
        
        # Add to results
        summaries.append({
            "video_id": video.video_id,
            "title": video.title,
            "author": video.author,
            "watch_date": video.watch_date.isoformat(),
            "summary": summary.summary,
            "key_points": summary.key_points,
            "learnings": summary.learnings
        })
    
    # Save results to file
    output_file = f"youtube_summaries_{datetime.now().strftime('%Y%m%d')}.json"
    with open(output_file, 'w') as f:
        json.dump({"summaries": summaries}, f, indent=2)
    
    print(f"\nSummaries saved to {output_file}")

if __name__ == '__main__':
    asyncio.run(main())