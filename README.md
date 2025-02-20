# YouTube Watch History Summarizer

This program fetches your YouTube watch history for the past week, retrieves video transcripts and descriptions, and generates AI-powered summaries with key points and learnings for each video.

## Setup

```shell
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt -U
```

2. Set up YouTube API credentials:
   - Go to the [Google Cloud Console](https://console.cloud.google.com/)
   - Create a new project or select an existing one
   - Enable the YouTube Data API v3
   - Create OAuth 2.0 credentials (Desktop application)
   - Download the client configuration file and save it as `client_secrets.json` in the project directory

3. Create a `.env.local` file with your API keys:
```
YOUTUBE_API_KEY=your_youtube_api_key
OPENAI_API_KEY=your_openai_api_key
```

## Usage

Run the program:
```bash
python app.py
```

The program will:
1. Authenticate with YouTube (first time will open a browser for OAuth)
2. Fetch your watch history for the past 7 days
3. Get transcripts and descriptions for each video
4. Generate summaries using OpenAI's GPT-4
5. Save results to a JSON file named `youtube_summaries_YYYYMMDD.json`

The output JSON will contain:
- Video details (ID, title, author, watch date)
- Summary of the video content
- Key points discussed
- Main learnings from the video

## Notes

- The program requires YouTube OAuth authentication to access your watch history
- Video transcripts are retrieved when available; otherwise, video descriptions are used
- Summaries are generated using OpenAI's GPT-4 model
- Results are saved in JSON format for easy parsing and integration with other tools