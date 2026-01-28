#!/usr/bin/env python3
"""
YouTube Video Discovery Script
Searches YouTube for videos and filters by view-to-subscriber multiplier.
"""

import os
import json
import argparse
from datetime import datetime, timedelta
from dotenv import load_dotenv
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Load environment variables
load_dotenv()

YOUTUBE_API_KEY = os.getenv('YOUTUBE_API_KEY')

def get_youtube_client():
    """Initialize YouTube API client."""
    if not YOUTUBE_API_KEY:
        raise ValueError("YOUTUBE_API_KEY not found in .env file")
    return build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)

def search_videos(youtube, query: str, days: int = 30, max_results: int = 50) -> list:
    """
    Search YouTube for videos matching query, published within last N days.
    Returns list of video IDs with basic info.
    """
    published_after = (datetime.utcnow() - timedelta(days=days)).isoformat() + 'Z'
    
    videos = []
    next_page_token = None
    
    while len(videos) < max_results:
        try:
            request = youtube.search().list(
                q=query,
                part='snippet',
                type='video',
                order='viewCount',
                publishedAfter=published_after,
                maxResults=min(50, max_results - len(videos)),
                pageToken=next_page_token
            )
            response = request.execute()
            
            for item in response.get('items', []):
                videos.append({
                    'video_id': item['id']['videoId'],
                    'title': item['snippet']['title'],
                    'channel_id': item['snippet']['channelId'],
                    'channel_name': item['snippet']['channelTitle'],
                    'published_at': item['snippet']['publishedAt'],
                    'thumbnail_url': item['snippet']['thumbnails'].get('high', {}).get('url', '')
                })
            
            next_page_token = response.get('nextPageToken')
            if not next_page_token:
                break
                
        except HttpError as e:
            print(f"YouTube API error: {e}")
            break
    
    return videos

def parse_duration(duration_str: str) -> int:
    """Parse ISO 8601 duration string (PT1H2M10S) to seconds."""
    import re
    match = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', duration_str)
    if not match:
        return 0
    
    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    seconds = int(match.group(3) or 0)
    
    return hours * 3600 + minutes * 60 + seconds

def get_video_stats(youtube, video_ids: list) -> dict:
    """
    Get view counts and duration for a list of video IDs.
    Returns dict: {video_id: {'viewCount': int, 'duration': int_seconds}}
    """
    stats = {}
    
    # YouTube API allows max 50 IDs per request
    for i in range(0, len(video_ids), 50):
        batch = video_ids[i:i+50]
        try:
            request = youtube.videos().list(
                part='statistics,contentDetails',
                id=','.join(batch)
            )
            response = request.execute()
            
            for item in response.get('items', []):
                view_count = int(item['statistics'].get('viewCount', 0))
                duration_iso = item['contentDetails'].get('duration', 'PT0S')
                duration_sec = parse_duration(duration_iso)
                
                stats[item['id']] = {
                    'viewCount': view_count,
                    'duration': duration_sec
                }
                
        except HttpError as e:
            print(f"Error fetching video stats: {e}")
    
    return stats

def get_channel_subscribers(youtube, channel_ids: list) -> dict:
    """
    Get subscriber counts for a list of channel IDs.
    Returns dict: {channel_id: subscriber_count}
    """
    subscribers = {}
    
    # Remove duplicates and batch
    unique_channels = list(set(channel_ids))
    
    for i in range(0, len(unique_channels), 50):
        batch = unique_channels[i:i+50]
        try:
            request = youtube.channels().list(
                part='statistics',
                id=','.join(batch)
            )
            response = request.execute()
            
            for item in response.get('items', []):
                # hiddenSubscriberCount means we can't get the count
                if item['statistics'].get('hiddenSubscriberCount', False):
                    subscribers[item['id']] = None
                else:
                    subscribers[item['id']] = int(item['statistics'].get('subscriberCount', 0))
                    
        except HttpError as e:
            print(f"Error fetching channel stats: {e}")
    
    return subscribers

def filter_by_multiplier(videos: list, video_stats: dict, channel_subs: dict, 
                        min_multiplier: float, min_views: int = 0, min_duration_sec: int = 0,
                        max_subs: int = 0) -> list:
    """
    Filter videos by view-to-subscriber multiplier, min views, duration, and max subs.
    Returns list of videos meeting constraints.
    """
    filtered = []
    
    for video in videos:
        stats = video_stats.get(video['video_id'], {'viewCount': 0, 'duration': 0})
        view_count = stats['viewCount']
        duration = stats['duration']
        sub_count = channel_subs.get(video['channel_id'])
        
        # Filter by Minimum Views
        if view_count < min_views:
            continue
            
        # Filter by Minimum Duration
        if duration < min_duration_sec:
            continue
        
        # Skip if subscriber count is hidden or zero
        if not sub_count or sub_count == 0:
            continue
        
        # Filter by Maximum Subscribers (find smaller channels)
        if max_subs > 0 and sub_count > max_subs:
            continue
        
        multiplier = view_count / sub_count
        
        if multiplier >= min_multiplier:
            video['view_count'] = view_count
            video['subscriber_count'] = sub_count
            video['duration_sec'] = duration
            video['multiplier'] = round(multiplier, 2)
            filtered.append(video)
    
    # Sort by multiplier (highest first)
    filtered.sort(key=lambda x: x['multiplier'], reverse=True)
    
    return filtered

def discover_videos(query: str, min_multiplier: float = 1.0, days: int = 30, max_results: int = 50, 
                    min_views: int = 0, min_duration_minutes: float = 0.0, max_subs: int = 0) -> dict:
    """
    Main function to discover high-performing YouTube videos.
    
    Args:
        query: Search query
        min_multiplier: Minimum view-to-subscriber ratio
        days: Number of days to look back
        max_results: Maximum videos to search
        min_views: Minimum view count
        min_duration_minutes: Minimum duration in minutes
        max_subs: Maximum subscriber count (0 = no limit)
    
    Returns:
        Dict with 'success', 'videos', and 'message' keys
    """
    try:
        youtube = get_youtube_client()
        
        # Step 1: Search for videos
        print(f"Searching for videos: '{query}' (past {days} days)...")
        videos = search_videos(youtube, query, days, max_results)
        
        if not videos:
            return {
                'success': True,
                'videos': [],
                'message': 'No videos found matching your query.'
            }
        
        print(f"Found {len(videos)} videos. Fetching statistics...")
        
        # Step 2: Get video view counts
        video_ids = [v['video_id'] for v in videos]
        video_stats = get_video_stats(youtube, video_ids)
        
        # Step 3: Get channel subscriber counts
        channel_ids = [v['channel_id'] for v in videos]
        channel_subs = get_channel_subscribers(youtube, channel_ids)
        
        # Step 4: Filter by multiplier and other criteria
        print(f"Filtering with min_multiplier={min_multiplier}, min_views={min_views}, max_subs={max_subs}...")
        filtered_videos = filter_by_multiplier(
            videos, 
            video_stats, 
            channel_subs, 
            min_multiplier,
            min_views=min_views,
            min_duration_sec=int(min_duration_minutes * 60),
            max_subs=max_subs
        )
        
        return {
            'success': True,
            'videos': filtered_videos,
            'message': f'Found {len(filtered_videos)} videos meeting criteria'
        }
        
    except ValueError as e:
        return {
            'success': False,
            'videos': [],
            'message': str(e)
        }
    except HttpError as e:
        if e.resp.status == 403:
            return {
                'success': False,
                'videos': [],
                'message': 'API quota exceeded. Please try again later.'
            }
        return {
            'success': False,
            'videos': [],
            'message': f'YouTube API error: {e}'
        }

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Search YouTube for high-performing videos')
    parser.add_argument('--query', '-q', required=True, help='Search query')
    parser.add_argument('--multiplier', '-m', type=float, default=1.0, help='Minimum view/subscriber multiplier')
    parser.add_argument('--days', '-d', type=int, default=30, help='Days to look back')
    parser.add_argument('--max-results', '-n', type=int, default=50, help='Max videos to search')
    parser.add_argument('--min-views', '-v', type=int, default=0, help='Minimum view count')
    parser.add_argument('--min-duration', '-t', type=float, default=0, help='Minimum duration in minutes')
    
    args = parser.parse_args()
    
    result = discover_videos(
        query=args.query,
        min_multiplier=args.multiplier,
        days=args.days,
        max_results=args.max_results,
        min_views=args.min_views,
        min_duration_minutes=args.min_duration
    )
    
    print(json.dumps(result, indent=2))
