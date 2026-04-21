import os
os.environ["ANONYMIZED_TELEMETRY"] = "false"

import json
from typing import List, Optional
from datetime import datetime, timedelta, timezone
from dateutil import parser
import argparse

import openai
from pydantic import BaseModel, SecretStr
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from browser_use import Agent, Controller, ActionResult
from browser_use.browser.browser import Browser, BrowserConfig
from browser_use.browser.context import BrowserContext

import asyncio
controller = Controller()
		# chrome_instance_path='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',


# Load environment variables from .env.local
load_dotenv('.env.local')

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
    video_id: Optional[str] = ""
    description: Optional[str] = ""
    transcript: Optional[str] = ""

    def __str__(self) -> str:
        """Return a human-readable string representation of the video."""
        watch_date_str = self.watch_date.strftime("%Y-%m-%d %H:%M:%S %Z")
        return f'"{self.title}" by {self.author} (watched on {watch_date_str})'
    
    def __repr__(self) -> str:
        """Return a detailed string representation of the video."""
        return (
            f'VideoInfo('
            f'title="{self.title}", '
            f'author="{self.author}", '
            f'watch_date="{self.watch_date.isoformat()}", '
            f'video_url="{self.video_url}", '
            f'video_id="{self.video_id}", '
            f'description="{self.description[:50]}{"..." if len(self.description) > 50 else ""}", '
            f'transcript_length={len(self.transcript) if self.transcript else 0}'
            f')'
        )
    
    def detailed_info(self) -> str:
        """Return a detailed, formatted string with all video information."""
        watch_date_str = self.watch_date.strftime("%Y-%m-%d %H:%M:%S %Z")
        return f"""
Title: {self.title}
Author: {self.author}
Watched: {watch_date_str}
URL: {self.video_url}
Video ID: {self.video_id or 'N/A'}
Description: {self.description or 'N/A'}
Has Transcript: {'Yes' if self.transcript else 'No'}
"""

class VideoInfoList(BaseModel):
    videos: List[VideoInfo]

    @property
    def sorted_videos(self) -> List[VideoInfo]:
        """
        Get videos sorted by watch_date in descending order (newest first).
        
        Returns:
            List[VideoInfo]: List of videos sorted by watch_date
        """
        return sorted(self.videos, key=lambda x: x.watch_date, reverse=True)

    def add_video(self, video: VideoInfo) -> None:
        """
        Add a new VideoInfo object to the videos list if it doesn't already exist.
        
        Args:
            video (VideoInfo): The VideoInfo object to add to the list
            
        Returns:
            None
        """
        # Check if video already exists by URL
        if not any(v.video_url == video.video_url for v in self.videos):
            self.videos.append(video)

    def __str__(self) -> str:
        """Return a human-readable string representation of the video list."""
        if not self.videos:
            return "No videos in list"
        
        video_count = len(self.videos)
        date_range = ""
        if video_count > 0:
            dates = [v.watch_date for v in self.videos]
            earliest = min(dates)
            latest = max(dates)
            date_range = f" (from {earliest.strftime('%Y-%m-%d')} to {latest.strftime('%Y-%m-%d')})"
        
        return f"{video_count} videos{date_range}:\n" + "\n".join(
            f"{i+1}. {str(video)}" 
            for i, video in enumerate(self.sorted_videos)
        )
    
    def __repr__(self) -> str:
        """Return a detailed string representation of the video list."""
        return f"VideoInfoList(videos=[{', '.join(repr(v) for v in self.sorted_videos)}])"
    
    def detailed_info(self) -> str:
        """Return a detailed, formatted string with all videos' information."""
        if not self.videos:
            return "No videos in list"
        
        video_count = len(self.videos)
        dates = [v.watch_date for v in self.videos]
        earliest = min(dates)
        latest = max(dates)
        
        header = f"""=== Video List Summary ===
Total Videos: {video_count}
Date Range: {earliest.strftime('%Y-%m-%d')} to {latest.strftime('%Y-%m-%d')}
=======================\n"""
        
        videos_info = "\n".join(
            f"=== Video {i+1} ===\n{video.detailed_info()}"
            for i, video in enumerate(self.sorted_videos)
        )
        
        return header + videos_info

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
        print("\nInput Videos:")
        for i, video in enumerate(params.videos, 1):
            if isinstance(video, VideoInfo):
                print(f"{i}. {video}")
            else:
                print(f"{i}. Invalid video type: {type(video)}")
    
    file_path = 'video_info.json'
    
    # Load existing data and add new videos
    existing_videos = load_video_info(file_path)
    for video in params.videos:
        print("------------------------------------------")
        print(f"Successfully loaded video: {video}")
        existing_videos.add_video(video)
    
    # Write the sorted videos to file
    print(f"\n--- Writing data to {file_path} ---")
    try:
        with open(file_path, 'w') as f:
            json.dump([video.model_dump() for video in existing_videos.sorted_videos], f, indent=2)
        print(f"Successfully wrote file")
    except Exception as e:
        print(f"Error writing file: {str(e)}")
        print(f"Error type: {type(e)}")
        print(f"Error details: {e.args}")
        return
    
    print(f"\n=== Completed save_video_info ===")
    print(f"Saved {len(params.videos)} new videos")
    print(f"Total videos in file: {len(existing_videos.videos)}")
    print("=====================================\n")

def parse_watch_date(date_str: str) -> datetime:
    """
    Parse a watch date string that might contain relative terms like 'Yesterday'.
    
    Args:
        date_str (str): Date string to parse, could be a standard date format or relative term
        
    Returns:
        datetime: Parsed datetime object in UTC timezone
    """
    # Convert common relative terms to dates
    date_str = date_str.lower().strip()
    now = datetime.now(timezone.utc)
    
    if date_str == 'today':
        return now
    elif date_str == 'yesterday':
        return now - timedelta(days=1)
    elif date_str.endswith(' days ago'):
        try:
            days = int(date_str.split(' ')[0])
            return now - timedelta(days=days)
        except (ValueError, IndexError):
            pass  # If parsing fails, fall through to dateutil parser
    elif date_str.endswith(' hours ago'):
        try:
            hours = int(date_str.split(' ')[0])
            return now - timedelta(hours=hours)
        except (ValueError, IndexError):
            pass  # If parsing fails, fall through to dateutil parser
    
    # For all other cases, use dateutil parser
    try:
        parsed_date = parser.parse(date_str)
        # Ensure timezone awareness
        if parsed_date.tzinfo is None:
            parsed_date = parsed_date.replace(tzinfo=timezone.utc)
        return parsed_date
    except Exception as e:
        print(f"Warning: Could not parse date '{date_str}', using current time")
        return now

def load_video_info(file_path: str) -> VideoInfoList:
    """
    Load video information from a JSON file and return a VideoInfoList object.
    
    Args:
        file_path (str): Path to the JSON file containing video information
        
    Returns:
        VideoInfoList: Object containing the loaded videos, empty list if file doesn't exist
                      or cannot be parsed
    """
    # if os.path.exists(file_path):
    #     try:
            # with open(file_path, 'r') as f:
            #     json_data = json.load(f)
            
            # if not json_data:
            #     print(f"Warning: Empty JSON data in {file_path}, starting fresh")
            #     return VideoInfoList(videos=[])
            
            # # Handle both nested and flat JSON structures
            # if isinstance(json_data, dict) and 'save_video_info' in json_data:
            #     existing_data = json_data['save_video_info'].get('videos', [])
            #     if not existing_data:
            #         print(f"Warning: No videos found in save_video_info structure")
            #         return VideoInfoList(videos=[])
            # else:
            #     existing_data = json_data if isinstance(json_data, list) else []
            #     if not isinstance(json_data, list):
            #         print(f"Warning: Expected list or dict with save_video_info, got {type(json_data)}")
                
            # print(f"Successfully loaded {len(existing_data)} existing videos")
            
            # Convert JSON data to VideoInfo objects
    #         videos = []
    #         for video in existing_data:
    #             try:
    #                 video_info = VideoInfo(
    #                     title=video['title'],
    #                     author=video['author'],
    #                     watch_date=parse_watch_date(video['watch_date']),
    #                     video_url=video['video_url'],
    #                     description=video.get('description', ''),
    #                     video_id=video.get('video_id', ''),
    #                     transcript=video.get('transcript', '')
    #                 )
    #                 videos.append(video_info)
    #                 print("------------------------------------------")
    #                 print(f"Successfully loaded video: {video_info}")
    #             except KeyError as ke:
    #                 print(f"Warning: Skipping video due to missing required field: {ke}")
    #             except Exception as e:
    #                 print(f"Warning: Skipping video due to error: {str(e)}")
    #                 continue
            
    #         return VideoInfoList(videos=videos)
            
    #     except json.JSONDecodeError:
    #         print(f"Warning: Could not parse existing {file_path}, starting fresh")
    #     except Exception as e:
    #         print(f"Error loading video info: {str(e)}")
    # else:
    #     print(f"No existing file found at {file_path}, will create new")
    
    return VideoInfoList(videos=[])

async def get_watch_history(days: int = 2) -> VideoInfoList:
    """
    Retrieve watch history using browser-use to access YouTube directly.
    
    Args:
        days (int): Number of days to look back in watch history (default: 2)
        
    Returns:
        VideoInfoList: Object containing the videos found
    """
    print(f"\nFetching watch history from the past {days} days...")
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
    5. For each batch of videos visible on the page, create a `VideoInfoList` object:
       - For each video, create a `VideoInfo` object with these details for each video
       - Add the `VideoInfo` object to the `VideoInfoList` object 
       - Scroll down to load more videos
       - Wait for the page to update
       - Stop if no new videos load or if we find videos older than {threshold_date.isoformat()}
    """    
    
    try:
        # Create and run the agent
        agent = Agent(
            task=tasklist_new,
            llm=ChatOpenAI(model="gpt-4o"),
            sensitive_data = sensitive_data,
            controller=controller,
            max_failures=1,
            generate_gif=False,
        )
        
        # Start the agent
        result = await agent.run()
        
        # Check if we need to handle 2FA
        if isinstance(result, str) and "2FA_REQUIRED" in result:
            await wait_for_user_2fa()
            # After 2FA is completed, continue with the history fetch
            result = await agent.run()
        
        print(f"""
        --------------------------------------------------------------------------
        """)
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
        print(f"Response content: {last_message}")
        # Convert the data into VideoInfo objects
        myVideoInfoList = VideoInfoList()
        for video in videos_data:
            print(f"Processing video: {video} <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<")
            try:
                # Extract video ID from URL if needed
                video_id = video.get('video_id')
                if not video_id and 'url' in video:
                    # Extract ID from URL like https://www.youtube.com/watch?v=VIDEO_ID
                    video_id = video['url'].split('v=')[-1].split('&')[0]
                
                # Parse the watch date
                watch_date = parse_watch_date(video['watch_date']).replace(tzinfo=timezone.utc)
                
                # Create VideoInfo object
                video_info = VideoInfo(
                    title=video['title'],
                    author=video['author'],
                    watch_date=watch_date,
                    video_url=video['video_url'],
                    description=video.get('description', '')
                )
                myVideoInfoList.add_video(video_info)
                print(f"Added video: {video_info.title}")
            except Exception as e:
                print(f"Error processing video data: {str(e)}")
                continue
        
        return myVideoInfoList
        
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
# 5. Function to Process Video Summaries
# -----------------------------------------------------------------------------------

async def process_video_summaries(videos: List[VideoInfo]) -> None:
    """
    Generate and save summaries for a list of videos.
    
    Args:
        videos (List[VideoInfo]): List of videos to generate summaries for
    """
    print(f"\n=== Starting Video Summary Processing ===")
    print(f"Generating summaries for {len(videos)} videos")
    
    summaries = []
    for video in videos:
        print(f"\nProcessing video: {video.title}")
        
        # Get transcript
        video_id = video.video_id or video.video_url.split('v=')[-1]  # Extract video ID from URL if not provided
        transcript = get_video_transcript(video_id)
        
        # Generate summary
        summary_request = VideoSummaryRequest(
            video_id=video_id,
            title=video.title,
            transcript=transcript if transcript else "",
            description=video.description or "",
            author=video.author
        )
        
        try:
            summary = await generate_video_summary(summary_request)
            
            # Add to results
            summaries.append({
                "video_id": video_id,
                "title": video.title,
                "author": video.author,
                "watch_date": video.watch_date.isoformat(),
                "summary": summary.summary,
                "key_points": summary.key_points,
                "learnings": summary.learnings
            })
        except Exception as e:
            print(f"Error generating summary for {video.title}: {str(e)}")
            continue
    
    if summaries:
        # Save results to file
        output_file = f"youtube_summaries_{datetime.now().strftime('%Y%m%d')}.json"
        with open(output_file, 'w') as f:
            json.dump({"summaries": summaries}, f, indent=2)
        print(f"\nSummaries saved to {output_file}")
    else:
        print("\nNo summaries were generated")

# -----------------------------------------------------------------------------------
# 6. Main Application Logic
# -----------------------------------------------------------------------------------

async def main():
    """
    Main application logic for finding and processing watched YouTube videos.
    """
    parser = argparse.ArgumentParser(description=f"""Find and process recently watched YouTube videos. 
Functionality currently requires an OpenAI API key.
""")
    parser.add_argument(
        '-d', '--days',
        type=int,
        default=2,
        help='Number of days to look back in watch history (default: 2)'
    )
    parser.add_argument(
        '--summarize',
        action='store_true',
        help='Generate summaries for the videos found'
    )
    args = parser.parse_args()

    print(f"\n=== Starting YouTube Watch History Processing ===")
    print(f"Looking back {args.days} days in watch history")
    
    try:
        # Get watch history
        myVideoInfoList: VideoInfoList = await get_watch_history(days=args.days)
        print(f"""Found {len(myVideoInfoList.videos)} videos""")
        if not myVideoInfoList.videos or len(myVideoInfoList.videos) == 0:
            print("No videos found in watch history")
            return
        print("------------------------------------------")
        print(f"Videos found:\n{myVideoInfoList}")
        exit(0)
        # Create VideoInfoList and save to file
        save_video_info(myVideoInfoList)

        exit(0)
        # Generate summaries if requested
        if args.summarize:
            await process_video_summaries(myVideoInfoList.sorted_videos)

    except Exception as e:
        print(f"Error in main: {str(e)}")
        raise

if __name__ == '__main__':
    asyncio.run(main())