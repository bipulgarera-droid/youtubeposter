#!/usr/bin/env python3
"""
YouTube Video Info Module
Fetches video details (tags, description, statistics) from YouTube Data API v3.
"""

import os
import requests
from typing import Dict, Optional, List


def get_video_details(video_id: str, api_key: str = None) -> Dict:
    """
    Fetch detailed video info from YouTube Data API.
    
    Returns:
        {
            "success": True/False,
            "video_id": "...",
            "title": "...",
            "description": "...",
            "tags": ["tag1", "tag2"],
            "categoryId": "...",
            "channelTitle": "...",
            "publishedAt": "...",
            "viewCount": 123456,
            "likeCount": 1234,
            "commentCount": 100,
            "duration": "PT12M34S",
            "thumbnails": {...}
        }
    """
    api_key = api_key or os.getenv('YOUTUBE_API_KEY') or os.getenv('GEMINI_API_KEY')
    
    if not api_key:
        return {"success": False, "error": "No API key found (set YOUTUBE_API_KEY or GEMINI_API_KEY)"}
    
    # Request snippet, contentDetails, and statistics
    url = "https://www.googleapis.com/youtube/v3/videos"
    params = {
        "key": api_key,
        "id": video_id,
        "part": "snippet,contentDetails,statistics"
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code != 200:
            return {"success": False, "error": f"API error: {response.status_code} - {response.text[:200]}"}
        
        data = response.json()
        
        if not data.get("items"):
            return {"success": False, "error": f"Video not found: {video_id}"}
        
        item = data["items"][0]
        snippet = item.get("snippet", {})
        content_details = item.get("contentDetails", {})
        statistics = item.get("statistics", {})
        
        return {
            "success": True,
            "video_id": video_id,
            "title": snippet.get("title", ""),
            "description": snippet.get("description", ""),
            "tags": snippet.get("tags", []),
            "categoryId": snippet.get("categoryId", ""),
            "channelTitle": snippet.get("channelTitle", ""),
            "publishedAt": snippet.get("publishedAt", ""),
            "thumbnails": snippet.get("thumbnails", {}),
            "duration": content_details.get("duration", ""),
            "dimension": content_details.get("dimension", ""),
            "viewCount": int(statistics.get("viewCount", 0)),
            "likeCount": int(statistics.get("likeCount", 0)),
            "commentCount": int(statistics.get("commentCount", 0))
        }
        
    except Exception as e:
        return {"success": False, "error": str(e)}


def get_multiple_video_details(video_ids: List[str], api_key: str = None) -> Dict:
    """
    Fetch details for multiple videos in one API call (up to 50).
    """
    api_key = api_key or os.getenv('YOUTUBE_API_KEY') or os.getenv('GEMINI_API_KEY')
    
    if not api_key:
        return {"success": False, "error": "No API key found"}
    
    # Join video IDs (max 50 per request)
    video_ids = video_ids[:50]
    ids_string = ",".join(video_ids)
    
    url = "https://www.googleapis.com/youtube/v3/videos"
    params = {
        "key": api_key,
        "id": ids_string,
        "part": "snippet,contentDetails,statistics"
    }
    
    try:
        response = requests.get(url, params=params, timeout=15)
        
        if response.status_code != 200:
            return {"success": False, "error": f"API error: {response.status_code}"}
        
        data = response.json()
        videos = []
        
        for item in data.get("items", []):
            snippet = item.get("snippet", {})
            content_details = item.get("contentDetails", {})
            statistics = item.get("statistics", {})
            
            videos.append({
                "video_id": item.get("id"),
                "title": snippet.get("title", ""),
                "description": snippet.get("description", ""),
                "tags": snippet.get("tags", []),
                "channelTitle": snippet.get("channelTitle", ""),
                "duration": content_details.get("duration", ""),
                "viewCount": int(statistics.get("viewCount", 0)),
                "likeCount": int(statistics.get("likeCount", 0))
            })
        
        return {"success": True, "videos": videos}
        
    except Exception as e:
        return {"success": False, "error": str(e)}


def format_duration(iso_duration: str) -> str:
    """
    Convert ISO 8601 duration (PT12M34S) to human readable (12:34).
    """
    import re
    match = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', iso_duration)
    if not match:
        return iso_duration
    
    hours, minutes, seconds = match.groups()
    hours = int(hours) if hours else 0
    minutes = int(minutes) if minutes else 0
    seconds = int(seconds) if seconds else 0
    
    if hours > 0:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    else:
        return f"{minutes}:{seconds:02d}"


if __name__ == "__main__":
    # Test with a sample video
    test_id = "dQw4w9WgXcQ"
    result = get_video_details(test_id)
    print(f"Title: {result.get('title')}")
    print(f"Tags: {result.get('tags', [])[:5]}")
