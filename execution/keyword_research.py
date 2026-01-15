#!/usr/bin/env python3
"""
Keyword Research Module
Uses YouTube Data API to analyze keyword difficulty and find opportunities.
"""

import os
import requests
import json
from typing import List, Dict, Optional
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

YOUTUBE_API_KEY = os.getenv('YOUTUBE_API_KEY')

def get_autocomplete_suggestions(seed_keyword: str, region: str = 'US') -> List[str]:
    """
    Get YouTube autocomplete suggestions for a seed keyword.
    Filters out non-English and irrelevant regional keywords.
    Also generates long-tail variations.
    """
    # Words to filter out (non-English, other regions, irrelevant)
    FILTER_WORDS = [
        # Languages
        'tamil', 'hindi', 'telugu', 'kannada', 'malayalam', 'marathi', 'bengali',
        'spanish', 'espanol', 'deutsch', 'french', 'japanese', 'korean', 'chinese',
        'arabic', 'russian', 'portuguese', 'italian', 'dutch', 'thai', 'vietnamese',
        # Other regions (when targeting US)
        'uk', 'australia', 'india', 'canada', 'germany', 'france', 'japan',
        'in india', 'in uk', 'in australia', 'in canada',
        # Irrelevant terms
        'app', 'game', 'song', 'movie', 'full movie', 'trailer', 'reaction',
        'meme', 'tiktok', 'shorts', 'asmr'
    ]
    
    # Long-tail modifiers to generate additional keywords
    LONG_TAIL_MODIFIERS = [
        'for beginners 2026',
        'how to start',
        'step by step guide',
        'vs stocks which is better',
        'best strategy 2026',
        'biggest mistakes to avoid',
        'what experts are saying',
        'complete guide for beginners',
        'pros and cons explained',
        'when to buy and sell'
    ]
    
    suggestions = []
    
    try:
        # Use the YouTube-specific autocomplete endpoint
        url = "https://clients1.google.com/complete/search"
        params = {
            'client': 'youtube',
            'hl': 'en',
            'gl': region.lower(),  # Add geolocation
            'gs_ri': 'youtube',
            'ds': 'yt',
            'q': seed_keyword
        }
        
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code == 200:
            text = response.text
            
            # Response format: window.google.ac.h([...])
            start_idx = text.find('[')
            end_idx = text.rfind(']') + 1
            
            if start_idx != -1 and end_idx > start_idx:
                json_str = text[start_idx:end_idx]
                data = json.loads(json_str)
                
                raw_suggestions = []
                if len(data) > 1 and isinstance(data[1], list):
                    for item in data[1]:
                        if isinstance(item, list) and len(item) > 0:
                            raw_suggestions.append(item[0])
                        elif isinstance(item, str):
                            raw_suggestions.append(item)
                
                # Filter out non-English and irrelevant keywords
                for kw in raw_suggestions:
                    kw_lower = kw.lower()
                    
                    # Skip if contains any filter word
                    should_skip = False
                    for fw in FILTER_WORDS:
                        if fw in kw_lower:
                            should_skip = True
                            break
                    
                    if not should_skip:
                        suggestions.append(kw)
    
    except Exception as e:
        print(f"Autocomplete error: {e}")
    
    # Generate long-tail variations
    long_tail = []
    seed_base = seed_keyword.split()[0] if seed_keyword else ""  # e.g., "silver" from "silver investing"
    
    for modifier in LONG_TAIL_MODIFIERS:
        long_tail_kw = f"{seed_keyword} {modifier}"
        if long_tail_kw not in suggestions:
            long_tail.append(long_tail_kw)
    
    # Also try with just the base word
    if seed_base and len(seed_keyword.split()) > 1:
        for modifier in LONG_TAIL_MODIFIERS[:5]:
            alt_kw = f"{seed_base} {modifier}"
            if alt_kw not in suggestions and alt_kw not in long_tail:
                long_tail.append(alt_kw)
    
    # Combine: filtered autocomplete + long-tail variations
    # Take up to 10 from autocomplete, then fill with long-tail
    final = suggestions[:10] + long_tail[:10]
    
    print(f"   Autocomplete: {len(suggestions)} filtered | Long-tail: {len(long_tail)} generated")
    
    return final[:20]  # Return up to 20 keywords


def search_youtube_videos(keyword: str, max_results: int = 15, region: str = 'US') -> List[Dict]:
    """
    Search YouTube for videos matching a keyword.
    Returns video IDs and basic info.
    
    Args:
        region: ISO 3166-1 alpha-2 country code (e.g., 'US', 'GB', 'IN')
    """
    if not YOUTUBE_API_KEY:
        print("ERROR: YOUTUBE_API_KEY not found")
        return []
    
    try:
        url = "https://www.googleapis.com/youtube/v3/search"
        params = {
            'key': YOUTUBE_API_KEY,
            'q': keyword,
            'part': 'snippet',
            'type': 'video',
            'maxResults': max_results,
            'order': 'relevance',
            'regionCode': region,
            'relevanceLanguage': 'en' if region in ['US', 'GB', 'CA', 'AU'] else None
        }
        # Remove None values
        params = {k: v for k, v in params.items() if v is not None}
        
        response = requests.get(url, params=params, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            videos = []
            for item in data.get('items', []):
                videos.append({
                    'video_id': item['id']['videoId'],
                    'title': item['snippet']['title'],
                    'channel_id': item['snippet']['channelId'],
                    'channel_title': item['snippet']['channelTitle'],
                    'published_at': item['snippet']['publishedAt']
                })
            return videos
        else:
            print(f"Search API error: {response.status_code} - {response.text[:200]}")
            return []
            
    except Exception as e:
        print(f"Search error: {e}")
        return []


def get_video_statistics(video_ids: List[str]) -> Dict[str, Dict]:
    """
    Get statistics for multiple videos (views, likes, comments).
    """
    if not YOUTUBE_API_KEY or not video_ids:
        return {}
    
    try:
        url = "https://www.googleapis.com/youtube/v3/videos"
        params = {
            'key': YOUTUBE_API_KEY,
            'id': ','.join(video_ids[:50]),  # Max 50 per request
            'part': 'statistics,contentDetails'
        }
        
        response = requests.get(url, params=params, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            stats = {}
            for item in data.get('items', []):
                vid = item['id']
                s = item.get('statistics', {})
                stats[vid] = {
                    'view_count': int(s.get('viewCount', 0)),
                    'like_count': int(s.get('likeCount', 0)),
                    'comment_count': int(s.get('commentCount', 0)),
                    'duration': item.get('contentDetails', {}).get('duration', '')
                }
            return stats
        
        return {}
    except Exception as e:
        print(f"Video stats error: {e}")
        return {}


def get_channel_statistics(channel_ids: List[str]) -> Dict[str, Dict]:
    """
    Get statistics for multiple channels (subscriber count).
    """
    if not YOUTUBE_API_KEY or not channel_ids:
        return {}
    
    try:
        # Deduplicate
        unique_ids = list(set(channel_ids))
        
        url = "https://www.googleapis.com/youtube/v3/channels"
        params = {
            'key': YOUTUBE_API_KEY,
            'id': ','.join(unique_ids[:50]),
            'part': 'statistics'
        }
        
        response = requests.get(url, params=params, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            stats = {}
            for item in data.get('items', []):
                cid = item['id']
                s = item.get('statistics', {})
                stats[cid] = {
                    'subscriber_count': int(s.get('subscriberCount', 0)),
                    'video_count': int(s.get('videoCount', 0))
                }
            return stats
        
        return {}
    except Exception as e:
        print(f"Channel stats error: {e}")
        return {}


def calculate_keyword_difficulty(videos: List[Dict], video_stats: Dict, channel_stats: Dict) -> Dict:
    """
    Calculate difficulty score for a keyword based on top video performance.
    
    Returns:
        - difficulty_score: 0-100 (higher = harder to rank)
        - difficulty_level: Low/Medium/High
        - avg_views: Average views of top videos
        - median_subs: Median subscriber count of top channels
        - opportunity_score: 0-100 (higher = better opportunity)
    """
    if not videos:
        return {
            'difficulty_score': 0,
            'difficulty_level': 'Unknown',
            'avg_views': 0,
            'median_subs': 0,
            'opportunity_score': 0,
            'top_videos': []
        }
    
    # Collect metrics
    view_counts = []
    sub_counts = []
    views_per_day = []
    
    top_videos = []
    
    for video in videos[:10]:  # Analyze top 10
        vid = video['video_id']
        cid = video['channel_id']
        
        v_stats = video_stats.get(vid, {})
        c_stats = channel_stats.get(cid, {})
        
        views = v_stats.get('view_count', 0)
        subs = c_stats.get('subscriber_count', 0)
        
        view_counts.append(views)
        sub_counts.append(subs)
        
        # Calculate views per day
        try:
            pub_date = datetime.fromisoformat(video['published_at'].replace('Z', '+00:00'))
            days_old = (datetime.now(timezone.utc) - pub_date).days or 1
            vpd = views / days_old
            views_per_day.append(vpd)
        except:
            views_per_day.append(0)
        
        top_videos.append({
            'title': video['title'][:60],
            'channel': video['channel_title'],
            'views': views,
            'subs': subs,
            'video_id': vid
        })
    
    # Calculate averages
    avg_views = sum(view_counts) / len(view_counts) if view_counts else 0
    
    # Median subscriber count
    sorted_subs = sorted(sub_counts)
    n = len(sorted_subs)
    median_subs = sorted_subs[n // 2] if n else 0
    
    avg_vpd = sum(views_per_day) / len(views_per_day) if views_per_day else 0
    
    # Calculate difficulty score (0-100)
    # Factors: avg views, median subs, competition intensity
    
    # Views component (0-40 points)
    if avg_views > 1000000:
        views_score = 40
    elif avg_views > 500000:
        views_score = 35
    elif avg_views > 100000:
        views_score = 28
    elif avg_views > 50000:
        views_score = 20
    elif avg_views > 10000:
        views_score = 12
    else:
        views_score = 5
    
    # Subscriber component (0-40 points)
    if median_subs > 1000000:
        subs_score = 40
    elif median_subs > 500000:
        subs_score = 32
    elif median_subs > 100000:
        subs_score = 24
    elif median_subs > 50000:
        subs_score = 16
    elif median_subs > 10000:
        subs_score = 10
    else:
        subs_score = 5
    
    # Velocity component (0-20 points) - how fast videos get views
    if avg_vpd > 10000:
        velocity_score = 20
    elif avg_vpd > 5000:
        velocity_score = 15
    elif avg_vpd > 1000:
        velocity_score = 10
    elif avg_vpd > 100:
        velocity_score = 5
    else:
        velocity_score = 2
    
    difficulty_score = views_score + subs_score + velocity_score
    
    # Difficulty level
    if difficulty_score >= 70:
        difficulty_level = 'High'
    elif difficulty_score >= 40:
        difficulty_level = 'Medium'
    else:
        difficulty_level = 'Low'
    
    # Opportunity score (inverse of difficulty, adjusted for potential)
    opportunity_score = max(0, 100 - difficulty_score)
    
    # Multiplier: How many views videos get relative to channel size
    # Higher multiplier = topic gets outsized views compared to channel authority
    multiplier = round(avg_views / median_subs, 1) if median_subs > 0 else 0
    
    return {
        'difficulty_score': difficulty_score,
        'difficulty_level': difficulty_level,
        'avg_views': int(avg_views),
        'median_subs': int(median_subs),
        'avg_views_per_day': int(avg_vpd),
        'opportunity_score': opportunity_score,
        'multiplier': multiplier,
        'top_videos': top_videos[:5]  # Return top 5 for display
    }


def research_keyword(keyword: str, region: str = 'US') -> Dict:
    """
    Full keyword research for a single keyword.
    """
    print(f"  Researching: {keyword}")
    
    # Search for videos
    videos = search_youtube_videos(keyword, max_results=15, region=region)
    
    if not videos:
        return {
            'keyword': keyword,
            'error': 'No videos found',
            'difficulty_score': 0,
            'difficulty_level': 'Unknown',
            'multiplier': 0
        }
    
    # Get video IDs and channel IDs
    video_ids = [v['video_id'] for v in videos]
    channel_ids = [v['channel_id'] for v in videos]
    
    # Fetch statistics
    video_stats = get_video_statistics(video_ids)
    channel_stats = get_channel_statistics(channel_ids)
    
    # Calculate difficulty
    metrics = calculate_keyword_difficulty(videos, video_stats, channel_stats)
    
    return {
        'keyword': keyword,
        **metrics
    }


def research_keywords(seed_keyword: str, include_suggestions: bool = True, region: str = 'US') -> Dict:
    """
    Research a seed keyword and its related suggestions.
    
    Args:
        seed_keyword: The main keyword to research
        include_suggestions: Whether to also research related keywords
        region: ISO 3166-1 alpha-2 country code (e.g., 'US', 'GB', 'IN')
    
    Returns:
        - seed_result: Research for the seed keyword
        - suggestions: List of related keyword research results
    """
    print(f"\n{'='*50}")
    print(f"KEYWORD RESEARCH: {seed_keyword} (Region: {region})")
    print(f"{'='*50}\n")
    
    results = {
        'seed_keyword': seed_keyword,
        'region': region,
        'seed_result': None,
        'suggestions': [],
        'quota_note': 'YouTube API quota: ~100 units used per keyword researched'
    }
    
    # Research the seed keyword
    print("📊 Analyzing seed keyword...")
    results['seed_result'] = research_keyword(seed_keyword, region=region)
    
    # Get suggestions if requested
    if include_suggestions:
        print("\n🔍 Getting related keywords...")
        suggestions = get_autocomplete_suggestions(seed_keyword, region=region)
        
        # Filter out the seed keyword itself
        suggestions = [s for s in suggestions if s.lower() != seed_keyword.lower()]
        
        print(f"   Found {len(suggestions)} suggestions")
        
        # Research each suggestion (up to 20)
        max_to_research = min(len(suggestions), 20)
        for i, suggestion in enumerate(suggestions[:20]):
            print(f"\n   [{i+1}/{max_to_research}] ", end='')
            result = research_keyword(suggestion, region=region)
            results['suggestions'].append(result)
    
    # Sort suggestions by opportunity score
    results['suggestions'].sort(key=lambda x: x.get('opportunity_score', 0), reverse=True)
    
    print(f"\n{'='*50}")
    print(f"Research complete! {1 + len(results['suggestions'])} keywords analyzed")
    print(f"{'='*50}\n")
    
    return results


if __name__ == '__main__':
    # Test
    import sys
    keyword = sys.argv[1] if len(sys.argv) > 1 else "silver investing"
    results = research_keywords(keyword)
    
    print("\n=== SEED KEYWORD ===")
    seed = results['seed_result']
    print(f"{seed['keyword']}: {seed['difficulty_level']} (Score: {seed['difficulty_score']})")
    print(f"  Avg Views: {seed['avg_views']:,} | Median Subs: {seed['median_subs']:,}")
    
    print("\n=== TOP OPPORTUNITIES ===")
    for s in results['suggestions'][:5]:
        print(f"{s['keyword']}: {s['difficulty_level']} (Opportunity: {s.get('opportunity_score', 0)})")
