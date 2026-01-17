"""
File Renamer - Rename output files based on topic.

Creates 3-word topic slugs for video and thumbnail files.
"""

import os
import re
import shutil
from typing import Tuple


def generate_topic_slug(topic: str, max_words: int = 3) -> str:
    """
    Generate a URL-safe topic slug from a topic string.
    
    Examples:
    - "Germany's $500 Billion Mistake" -> "germanyenergycrisis"
    - "Why France is POORER Than You Think" -> "franceeconomicdecline"
    - "The Slow DEATH of The Petrodollar" -> "petrodollardeath"
    """
    # Remove special characters
    clean = re.sub(r'[^\w\s]', '', topic.lower())
    
    # Split into words
    words = clean.split()
    
    # Remove common filler words
    stopwords = {
        'the', 'a', 'an', 'is', 'are', 'was', 'were', 'of', 'in', 'to', 
        'for', 'on', 'with', 'at', 'by', 'from', 'why', 'how', 'what',
        'than', 'you', 'think', 'and', 'or', 'but', 'that', 'this',
        'its', 'not', 'it', 'be', 'as', 'they', 'their', 'there', 'test'
    }
    
    meaningful_words = [w for w in words if w not in stopwords and len(w) > 2]
    
    # Take first N meaningful words
    slug_words = meaningful_words[:max_words]
    
    # Join WITHOUT dashes (user preference)
    slug = ''.join(slug_words)
    
    return slug or 'video'


def rename_video_file(video_path: str, topic: str) -> str:
    """
    Rename video file based on topic.
    
    Returns new file path.
    """
    if not os.path.exists(video_path):
        return video_path
    
    directory = os.path.dirname(video_path)
    extension = os.path.splitext(video_path)[1]
    
    slug = generate_topic_slug(topic)
    new_filename = f"{slug}{extension}"
    new_path = os.path.join(directory, new_filename)
    
    # Handle existing file
    counter = 1
    while os.path.exists(new_path) and new_path != video_path:
        new_filename = f"{slug}-{counter}{extension}"
        new_path = os.path.join(directory, new_filename)
        counter += 1
    
    if new_path != video_path:
        shutil.move(video_path, new_path)
    
    return new_path


def rename_thumbnail_file(thumbnail_path: str, topic: str) -> str:
    """
    Rename thumbnail file based on topic.
    
    Returns new file path.
    """
    return rename_video_file(thumbnail_path, topic)  # Same logic


def rename_output_files(video_path: str, thumbnail_path: str, topic: str) -> Tuple[str, str]:
    """
    Rename both video and thumbnail files for upload.
    
    Returns (new_video_path, new_thumbnail_path)
    """
    new_video = rename_video_file(video_path, topic)
    new_thumbnail = rename_thumbnail_file(thumbnail_path, topic)
    
    return new_video, new_thumbnail


def extract_topic_from_title(title: str) -> str:
    """
    Extract core topic from a video title.
    
    Examples:
    - "Why France is POORER Than You Think (The Economic Truth)" -> "France Economy"
    - "Germany's $500 Billion Mistake (The Green Energy Trap)" -> "Germany Energy"
    """
    # Remove parenthetical
    clean = re.sub(r'\([^)]*\)', '', title)
    
    # Remove common patterns
    clean = re.sub(r"Why |How |The |'s ", ' ', clean)
    clean = re.sub(r'[^\w\s]', '', clean)
    
    words = clean.split()
    
    # Get first 2-3 meaningful words
    stopwords = {'is', 'are', 'was', 'than', 'you', 'think', 'became', 'got'}
    meaningful = [w for w in words if w.lower() not in stopwords]
    
    return ' '.join(meaningful[:3])


if __name__ == "__main__":
    # Test
    test_topics = [
        "Germany's $500 Billion Mistake (The Green Energy Trap)",
        "Why France is POORER Than You Think (The Economic Truth)",
        "The Slow DEATH of The Petrodollar (And What Comes Next)",
        "Why Italy Can't Grow (The Curse of The Lira)",
        "How Norway Got Rich (And Why They Don't Spend It)"
    ]
    
    print("Topic slug tests:")
    for topic in test_topics:
        slug = generate_topic_slug(topic)
        extracted = extract_topic_from_title(topic)
        print(f"\n{topic}")
        print(f"  Slug: {slug}")
        print(f"  Topic: {extracted}")
