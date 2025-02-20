# lets save some claude-generated VideoInfoList data to test-video-info.json
# this is a test of the brower-use action
# so we need to have the save file function as a action and then call it from inside a short task description


import os
os.environ["ANONYMIZED_TELEMETRY"] = "false"
import json
from typing import Any
from typing import List, Optional

from pydantic import BaseModel, Field, SecretStr
from datetime import datetime, timedelta, timezone
from dateutil import parser



import openai
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from browser_use import Agent, Controller, ActionResult
import asyncio
controller = Controller()

# Load environment variables from .env.local
load_dotenv('.env.local')


class VideoInfo(BaseModel):
    video_url: str
    title: str
    author: str
    watch_date: datetime
    description: str

class VideoInfoList(BaseModel):
    videos: list[VideoInfo]

    class Config:
        arbitrary_types_allowed = True

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
    return

def createVideoInfoList() -> VideoInfoList:
    return VideoInfoList(
        videos=[
            VideoInfo(
                video_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                title="The Best Video Ever",
                author="Claude",
                watch_date=datetime.now(),
                description="This is the best video ever. You should watch it."
            ),
            VideoInfo(
                video_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                title="The Worst Video Ever",
                author="Claude",
                watch_date=datetime.now(),
                description="This is the worst video ever. You should avoid it."
            ),
            VideoInfo(
                video_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                title="The 3rd Video Ever",
                author="Claude",
                watch_date=datetime.now(),
                description="This is the 3rd video ever. You should watch it."
            ),
            VideoInfo(
                video_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                title="The 4th Video Ever",
                author="Claude",
                watch_date=datetime.now(),
                description="This is the 4th video ever. You should watch it."
            ),
            VideoInfo(
                video_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                title="The 5th Video Ever",
                author="Claude",
                watch_date=datetime.now(),
                description="This is the 5th video ever. You should watch it."
            )
        ]
    )
def main():
    video_info_list = createVideoInfoList()
    print("=====================================\n")

    print(video_info_list.model_dump_json(indent=2))
    
    with open('test-video-info.json', 'w') as f:
        json.dump(video_info_list, f, indent=2)