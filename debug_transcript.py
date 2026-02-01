from youtube_transcript_api import YouTubeTranscriptApi
import sys

video_id = "v5ZsgVyTXj8" # v5ZsgVyTXj8 (The failing video)
print(f"--- Debugging Transcript for {video_id} ---")

# 1. Test Instance API
# test_instance_api(video_id) # This function is not defined in the original code, commenting out for syntax correctness.

# 2. Test Fallback (yt-dlp) - mocked or real?
# For now, just test the API as that's the primary method.

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

