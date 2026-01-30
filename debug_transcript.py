from youtube_transcript_api import YouTubeTranscriptApi
import sys

video_id = "v5ZsgVyTXj8"

print(f"Testing transcript for {video_id}...")

try:
    print("--- Method 1: Instance-based list() ---")
    api = YouTubeTranscriptApi()
    transcript_list = api.list(video_id)
    print("Transcripts found!")
    for t in transcript_list:
        print(f"  {t.language_code} ({t.language}) - Generated: {t.is_generated}")
    
    transcript = transcript_list.find_transcript(['en', 'en-US'])
    data = transcript.fetch()
    print(f"Fetched {len(data)} lines.")

except Exception as e:
    print(f"Method 1 Failed: {e}")

