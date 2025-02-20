import os
import json
from datetime import datetime, timezone, timedelta
from typing import List, Dict
import argparse
from pathlib import Path
import sys
import logging

from pydantic import BaseModel, SecretStr
from dotenv import load_dotenv
from browser_use import Agent
from langchain_openai import ChatOpenAI

# Configure logging to minimize sensitive data exposure
logging.getLogger("browser_use").setLevel(logging.WARNING)
os.environ["ANONYMIZED_TELEMETRY"] = "false"

class Credentials(BaseModel):
    """Secure storage for credentials using Pydantic's SecretStr"""
    google_username: SecretStr
    google_password: SecretStr
    openai_api_key: SecretStr

class VideoInfo(BaseModel):
    video_url: str
    watch_timestamp: datetime

def load_credentials() -> Credentials:
    """
    Load credentials from .env.local file securely.
    
    Returns:
        Credentials: Secure credential object
        
    Raises:
        ValueError: If any required credentials are missing
    """
    load_dotenv('.env.local')
    
    # Load credentials
    username = os.getenv('GOOGLE_USERNAME')
    password = os.getenv('GOOGLE_PASSWORD')
    openai_key = os.getenv('OPENAI_API_KEY')
    
    # Validate all required credentials are present
    missing = []
    if not username:
        missing.append('GOOGLE_USERNAME')
    if not password:
        missing.append('GOOGLE_PASSWORD')
    if not openai_key:
        missing.append('OPENAI_API_KEY')
    
    if missing:
        raise ValueError(
            f"Missing required credentials in .env.local: {', '.join(missing)}\n"
            "Please ensure all required credentials are set in your .env.local file."
        )
    
    # Return credentials as secure Pydantic model
    return Credentials(
        google_username=SecretStr(username),
        google_password=SecretStr(password),
        openai_api_key=SecretStr(openai_key)
    )

async def get_watch_history(start_date: datetime, end_date: datetime) -> List[VideoInfo]:
    """
    Retrieve watch history from YouTube between start_date and end_date.
    
    Args:
        start_date: Start date to look for videos
        end_date: End date to look for videos
        
    Returns:
        List[VideoInfo]: List of videos watched in the date range
    """
    # Load credentials securely
    creds = load_credentials()
    
    # Create agent with specific task
    agent = Agent(
        task=f"""Go to YouTube watch history at https://myactivity.google.com/product/youtube/?hl=en and collect videos watched between {start_date.date()} and {end_date.date()}.
        
        Important: The page uses infinite scroll. Follow these steps carefully:
        1. Navigate to the login page
        2. If 2FA is required, wait for user to complete it
        3. Once logged in, start collecting videos:
           - For each visible video entry, extract:
             * The video URL from the link to the video
             * The watch timestamp, handling symbolic dates:
               - For "today": Use the exact time with today's date ({datetime.now().date()})
               - For "yesterday": Use the exact time with yesterday's date ({(datetime.now() - timedelta(days=1)).date()})
               - For other dates: Combine the date shown with the time shown
           - After processing visible entries:
             * Scroll to the bottom of the page using document.documentElement.scrollHeight
             * Wait for new content to load (look for new video entries)
             * If no new entries appear after scrolling, we've reached the end
           - Keep scrolling and collecting until either:
             a) You find a video older than {start_date.date()}, then stop
             b) No more videos load after scrolling
        4. For each collected video, ensure:
           - video_url: The full YouTube video URL
           - watch_timestamp: The exact watch time in ISO format (YYYY-MM-DDTHH:mm:ss.sssZ)
             Example: If a video was watched "today at 3:45 PM", convert it to "{datetime.now().replace(hour=15, minute=45, second=0, microsecond=0).isoformat()}"
        
        Return the data as a list of VideoInfo objects.
        """,
        llm=ChatOpenAI(
            model="chatgpt-4o-latest",
            openai_api_key=creds.openai_api_key.get_secret_value(),
            temperature=0
        ),
        # Pass credentials securely through sensitive_data
        sensitive_data={
            'google_username': creds.google_username.get_secret_value(),
            'google_password': creds.google_password.get_secret_value()
        }
    )
    
    try:
        # Execute the task
        result = await agent.run()
        
        # Debug the result
        print("\nDEBUG: Agent Result:")
        print(f"Type: {type(result)}")
        print(f"Raw Content: {result}")
        print("\nDEBUG: Result Attributes:")
        for attr in dir(result):
            if not attr.startswith('_'):  # Skip private attributes
                try:
                    value = getattr(result, attr)
                    print(f"{attr}: {value}")
                except Exception as e:
                    print(f"{attr}: Error getting value - {e}")
        
        # Try to get the last response
        try:
            if hasattr(result, 'history') and result.history:
                print("\nDEBUG: Last Response:")
                print(result.history[-1])
                
                # Print all history for debugging scroll issues
                print("\nDEBUG: Full History:")
                for i, hist in enumerate(result.history):
                    print(f"\nStep {i}:")
                    print(hist)
        except Exception as e:
            print(f"Error getting last response: {e}")
        
        # Parse results and create VideoInfo objects
        videos = []
        if isinstance(result, dict) and "items" in result:
            for item in result['items']:
                try:
                    video = VideoInfo(
                        video_url=item["video_url"],
                        watch_timestamp=datetime.fromisoformat(item["watch_timestamp"])
                    )
                    if start_date <= video.watch_timestamp <= end_date:
                        videos.append(video)
                except (KeyError, ValueError) as e:
                    print(f"Error processing video: {e}")
                    continue
        
        if videos:
            print(f"Found {len(videos)} videos in the specified date range")
        else:
            print("No videos found in the specified date range")
        
        return videos
    
    except Exception as e:
        print(f"Error during watch history collection: {e}")
        raise

def save_video_info(videos: List[VideoInfo], start_date: datetime, end_date: datetime, output_dir: str):
    """Save video information to JSON file."""
    # Create filename with date range
    filename = f"{output_dir}/watched_{start_date.date()}-{end_date.date()}.json"
    
    # Convert to JSON-serializable format
    video_data = [
        {
            "video_url": v.video_url,
            "watch_timestamp": v.watch_timestamp.isoformat()
        }
        for v in videos
    ]
    
    # Save to file
    with open(filename, 'w') as f:
        json.dump(video_data, f, indent=2)
    
    print(f"Saved {len(videos)} videos to {filename}")

async def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description='Fetch YouTube watch history and save to JSON',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Get videos watched in the last 7 days
  python find-watched.py --days 7
  
  # Get videos between specific dates
  python find-watched.py --start-date 2024-02-01 --end-date 2024-02-15
  
  # Get videos since a specific date until today
  python find-watched.py --start-date 2024-02-01
  
Note:
  - Dates should be in YYYY-MM-DD format
  - Times are in UTC
  - Results will be saved to data/watched_<start_date>-<end_date>.json
  - Credentials should be in .env.local file as GOOGLE_USERNAME and GOOGLE_PASSWORD
"""
    )
    
    # Create a mutually exclusive group for date range specification
    date_group = parser.add_mutually_exclusive_group(required=True)
    date_group.add_argument(
        '--days',
        type=int,
        help='Number of days to look back from today'
    )
    date_group.add_argument(
        '--start-date',
        help='Start date (YYYY-MM-DD)'
    )
    
    parser.add_argument(
        '--end-date',
        help='End date (YYYY-MM-DD), defaults to today'
    )
    
    parser.add_argument(
        '--output-dir',
        default='data',
        help='Directory to save results (default: data)'
    )
    
    args = parser.parse_args()
    
    # Calculate start and end dates based on input
    end_date = None
    if args.end_date:
        end_date = datetime.fromisoformat(args.end_date).replace(tzinfo=timezone.utc)
    else:
        end_date = datetime.now(timezone.utc)
    
    if args.days:
        start_date = end_date - timedelta(days=args.days)
    else:
        start_date = datetime.fromisoformat(args.start_date).replace(tzinfo=timezone.utc)
    
    try:
        # Create output directory
        Path(args.output_dir).mkdir(exist_ok=True)
        
        # Get watch history
        print(f"Fetching videos from {start_date.date()} to {end_date.date()}...")
        videos = await get_watch_history(start_date, end_date)
        
        # Save results
        save_video_info(videos, start_date, end_date, args.output_dir)
        
    except ValueError as ve:
        print(f"Error: {ve}")
        parser.print_help()
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        raise

if __name__ == '__main__':
    import asyncio
    asyncio.run(main())
