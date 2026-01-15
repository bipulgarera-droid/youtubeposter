# Video Transcription

**Goal:** Download audio from a YouTube video and transcribe it using Gemini 2.5 Flash.

**Inputs:**
- `video_url`: YouTube video URL (e.g., "https://youtube.com/watch?v=VIDEO_ID")
- `video_id`: Optional, extracted from URL if not provided

**Outputs:**
- `transcript`: Full text transcription of the video
- `audio_path`: Path to downloaded audio file (in `.tmp/audio/`)

**Tools/Scripts:**
- `execution/transcribe_video.py`

**Dependencies:**
- `yt-dlp` for downloading audio
- `google-generativeai` for Gemini API
- Requires `GEMINI_API_KEY` in `.env`

**Edge Cases:**
- Age-restricted videos: May fail to download, return error
- Very long videos (>2 hours): May hit Gemini context limits, suggest splitting
- Private/deleted videos: Return appropriate error message
- Audio download fails: Retry once, then return error

**Steps:**
1. Extract video ID from URL
2. Download audio using yt-dlp to `.tmp/audio/{video_id}.mp3`
3. Upload audio file to Gemini
4. Request transcription with Gemini 2.5 Flash
5. Return transcript text
6. Optionally clean up audio file
