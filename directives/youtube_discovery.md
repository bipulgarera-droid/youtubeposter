# YouTube Video Discovery

**Goal:** Search YouTube for videos in a specific niche/topic and filter by view-to-subscriber multiplier to find high-performing content.

**Inputs:**
- `query`: Search query (niche + subtopic, e.g., "Venezuela finance impact")
- `multiplier`: Minimum view-to-subscriber ratio (e.g., 1.5 means views should be 1.5x subscribers)
- `days`: Number of days to look back (default: 30)
- `max_results`: Maximum videos to return (default: 50)

**Outputs:**
- JSON array of videos with: `video_id`, `title`, `channel_name`, `subscriber_count`, `view_count`, `published_at`, `multiplier`, `thumbnail_url`

**Tools/Scripts:**
- `execution/youtube_search.py`

**API Used:**
- YouTube Data API v3 (requires `YOUTUBE_API_KEY` in `.env`)

**Edge Cases:**
- Channels with hidden subscriber counts: Skip these videos
- Videos with 0 views: Skip (avoid division issues)
- API quota exceeded: Return error with suggestion to wait
- No videos match multiplier: Return empty array with message

**Steps:**
1. Build YouTube API client with API key from `.env`
2. Search videos by query with `publishedAfter` filter (past N days)
3. For each video, fetch channel statistics to get subscriber count
4. Calculate multiplier: `view_count / subscriber_count`
5. Filter videos where multiplier >= input threshold
6. Sort by multiplier (highest first)
7. Return filtered list as JSON
