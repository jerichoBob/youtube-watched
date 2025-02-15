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
from browser_use import Agent, Controller, ActionResult
import asyncio
controller = Controller()

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
    title: str
    author: str
    watch_date: datetime
    video_url: str
    description: Optional[str] = ""

class VideoInfoList(BaseModel):
    videos: List[VideoInfo]

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


@controller.action('Give a prompt to ask the human to complete 2FA')
async def ask_human(prompt: str) -> str:
    answer = input(f'\n{prompt}\nInput: ')
    return ActionResult(extracted_content=answer)

@controller.action('Save VideoInfo', param_model=VideoInfoList)
def save_video_info(params: VideoInfoList):
    """Save VideoInfo objects to JSON file with deduplication.
    
    Args:
        params (VideoInfoList): A Pydantic model containing a list of VideoInfo objects
                              Each VideoInfo has: title, author, watch_date, video_url, description
    """
    print(f"\n=== Starting save_video_info ===")
    print(f"Input params type: {type(params)}")
    if hasattr(params, 'videos'):
        print(f"Number of videos in input: {len(params.videos)}")
        print(f"First video sample: {params.videos[0] if params.videos else 'No videos'}")
    
    file_path = 'video_info.json'
    existing_data = []
    
    # Read existing data if file exists
    print(f"\n--- Reading existing data from {file_path} ---")
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r') as f:
                existing_data = json.load(f)
            print(f"Successfully loaded {len(existing_data)} existing videos")
        except json.JSONDecodeError:
            print(f"Warning: Could not parse existing {file_path}, starting fresh")
    else:
        print(f"No existing file found at {file_path}, will create new")
    
    # Convert new VideoInfo objects to dict
    print("\n--- Converting VideoInfo objects to dict ---")
    try:
        new_videos = [
            {
                'video_url': video.video_url,
                'title': video.title,
                'author': video.author,
                'watch_date': video.watch_date.isoformat(),
                'description': video.description
            }
            for video in params.videos
        ]
        print(f"Successfully converted {len(new_videos)} videos")
        print(f"Sample converted video: {new_videos[0] if new_videos else 'No videos'}")
    except Exception as e:
        print(f"Error converting videos to dict: {str(e)}")
        print(f"Videos data: {params.videos}")
        return
    
    # Combine existing and new data, using video_url as unique key
    print("\n--- Combining existing and new data ---")
    try:
        video_dict = {video['video_url']: video for video in existing_data}
        print(f"Created dict from {len(video_dict)} existing videos")
        
        video_dict.update({video['video_url']: video for video in new_videos})
        print(f"Updated dict with new videos, now contains {len(video_dict)} videos")
    except Exception as e:
        print(f"Error combining data: {str(e)}")
        return
    
    # Convert back to list and sort by watch_date
    print("\n--- Sorting combined videos ---")
    try:
        combined_videos = list(video_dict.values())
        combined_videos.sort(key=lambda x: x['watch_date'], reverse=True)
        print(f"Successfully sorted {len(combined_videos)} videos")
    except Exception as e:
        print(f"Error sorting videos: {str(e)}")
        return
    
    # Write the combined data back to file
    print(f"\n--- Writing data to {file_path} ---")
    try:
        with open(file_path, 'w') as f:
            json.dump(combined_videos, f, indent=2)
        print(f"Successfully wrote file")
    except Exception as e:
        print(f"Error writing file: {str(e)}")
        return
    
    print(f"\n=== Completed save_video_info ===")
    print(f"Saved {len(new_videos)} new videos")
    print(f"Total videos in file: {len(combined_videos)}")
    print("=====================================\n")


async def get_watch_history(days: int = 2) -> List[VideoInfo]:
    """
    Retrieve watch history using browser-use to access YouTube directly.
    """
    print("\nFetching watch history from the past 7 days...")
    threshold_date = datetime.now(timezone.utc) - timedelta(days=days)
    
    # Get credentials from environment
    un, pw = get_google_credentials()
    sensitive_data = {'google_username': un, 'google_password': pw}

    tasklist_new = f"""
    1. Go to https://myactivity.google.com/product/youtube/?hl=en
    2. If not signed in:
       - Sign in with google_username and google_password
       - If 2FA is detected, print "2FA_REQUIRED" and wait for user input
    4. Wait for the page to load completely. This page has infinite scroll, so when you scroll, wait for the page to update. Scroll until you meet the time-period search criteria
    5. For each batch of videos visible on the page, create a VideoInfoList object:
       - For each video, create a VideoInfo object with these details for each video:
         * title
         * author (channel name)
         * watch date
         * video URL (to get video_id)
         * description (if available)
    6. Once the VideoInfoList objects are created:
       - Sort them by watch date (newest first)
       - Save the VideoInfoList object using the `save_video_info` action
       - Scroll down to load more videos
       - Wait for the page to update
       - Stop if no new videos load or if we find videos older than {threshold_date.isoformat()}
    6. Exit when done
    """    
    
    try:
        # Create and run the agent
        agent = Agent(
            task=tasklist_new,
            llm=ChatOpenAI(model="gpt-4o"),
            sensitive_data = sensitive_data,
            controller=controller
        )
        
        # Start the agent
        result = await agent.run()
        
        # Check if we need to handle 2FA
        if isinstance(result, str) and "2FA_REQUIRED" in result:
            await wait_for_user_2fa()
            # After 2FA is completed, continue with the history fetch
            result = await agent.run()
        
        # Extract the last message content from the agent history
        if hasattr(result, 'messages') and result.messages:
            last_message = result.messages[-1].content
            try:
                videos_data = json.loads(last_message)
            except json.JSONDecodeError as e:
                print(f"Error parsing agent response as JSON: {str(e)}")
                print(f"Response content: {last_message}")
                return []
        else:
            print("No valid response from agent")
            return []
        
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