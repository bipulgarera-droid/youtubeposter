#!/usr/bin/env python3
"""
Metadata Generation - Generate optimized titles, descriptions, and tags.
Creates modified metadata based on reference video while maintaining SEO value.
"""
import os
import re
import json
from typing import Dict, List, Optional
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()

GEMINI_API_KEY = os.getenv('GEMINI_API_KEY') or os.getenv('GOOGLE_API_KEY')
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)


def generate_modified_title(original_title: str, topic: str, script_hook: str = "") -> str:
    """
    Generate a modified title that's 80-90% similar to original.
    Keeps core keywords but changes a few words to be unique.
    """
    prompt = f"""Generate a YouTube video title based on this reference:

ORIGINAL TITLE: {original_title}
TOPIC: {topic}
SCRIPT HOOK: {script_hook[:200] if script_hook else 'N/A'}

RULES:
1. Keep 80-90% of the original meaning and keywords
2. Change 2-3 words to make it unique
3. Keep it under 60 characters
4. Maintain urgency and curiosity
5. Do NOT use asterisks or markdown
6. Return ONLY the new title, nothing else

NEW TITLE:"""

    try:
        model = genai.GenerativeModel('gemini-2.0-flash')
        response = model.generate_content(prompt)
        title = response.text.strip()
        # Clean up any quotes or extra formatting
        title = title.strip('"\'')
        title = re.sub(r'^(New Title:|Title:)\s*', '', title, flags=re.IGNORECASE)
        return title[:100]  # Max 100 chars
    except Exception as e:
        print(f"Title generation failed: {e}")
        return original_title


def generate_description(
    script_text: str,
    topic: str,
    original_description: str = "",
    timestamps_text: str = "",
    include_timestamps: bool = True
) -> str:
    """
    Generate an optimized YouTube description with timestamps.
    Uses the hook from the script and adds SEO elements.
    
    Args:
        script_text: Full script text
        topic: Video topic
        original_description: Reference description for style
        timestamps_text: Pre-formatted timestamps (from generate_timestamps.py)
        include_timestamps: Whether to include timestamps section
    """
    # Extract first 2-3 sentences as hook
    sentences = re.split(r'(?<=[.!?])\s+', script_text)
    hook = ' '.join(sentences[:3])[:300]
    
    prompt = f"""Generate a YouTube video description:

SCRIPT HOOK: {hook}
TOPIC: {topic}
REFERENCE DESCRIPTION (for style): {original_description[:500] if original_description else 'N/A'}

STRUCTURE:
1. First 2 sentences: Compelling hook from the script (this shows in search results)
2. Line break, then "In this video, we cover:" with 3-5 bullet points
3. Line break, then call to action (subscribe, comment)
4. Line break, then disclaimer if financial content

RULES:
- Keep it under 500 characters for the main content
- Use plain text only - NO asterisks, NO markdown, NO bold
- Use emoji sparingly (1-2 max)
- Do NOT include timestamps - they will be added separately
- Include 2-3 relevant hashtags at the end

DESCRIPTION:"""

    try:
        model = genai.GenerativeModel('gemini-2.0-flash')
        response = model.generate_content(prompt)
        description = response.text.strip()
        # Remove any markdown
        description = description.replace('*', '')
        description = description.replace('_', '')
        
        # Add timestamps if provided
        if include_timestamps and timestamps_text:
            description = description + "\n\n" + timestamps_text
        
        return description
    except Exception as e:
        print(f"Description generation failed: {e}")
        # Fallback to simple description
        fallback = f"{hook}\n\n{topic}\n\nSubscribe for more updates!"
        if timestamps_text:
            fallback += "\n\n" + timestamps_text
        return fallback



def extract_and_generate_tags(
    topic: str,
    original_tags: List[str] = None,
    script_text: str = ""
) -> List[str]:
    """
    Generate tags combining original video tags with topic keywords.
    """
    prompt = f"""Generate YouTube tags for this video:

TOPIC: {topic}
ORIGINAL TAGS: {', '.join(original_tags[:10]) if original_tags else 'None'}
SCRIPT EXCERPT: {script_text[:500]}

Generate 15-20 relevant tags. Return as comma-separated list.
Include: topic keywords, related terms, audience keywords, trending terms.
Keep each tag under 30 characters.

TAGS:"""

    try:
        model = genai.GenerativeModel('gemini-2.0-flash')
        response = model.generate_content(prompt)
        tags_text = response.text.strip()
        # Parse comma-separated tags
        tags = [t.strip() for t in tags_text.split(',')]
        # Clean tags
        tags = [re.sub(r'[^\w\s-]', '', t) for t in tags]
        tags = [t for t in tags if t and len(t) <= 30]
        
        # Add original tags if available
        if original_tags:
            for tag in original_tags[:5]:
                if tag not in tags:
                    tags.append(tag)
        
        return tags[:20]  # YouTube allows max ~500 chars total
    except Exception as e:
        print(f"Tag generation failed: {e}")
        # Fallback
        return topic.lower().split()[:10]


def generate_full_metadata(
    original_title: str,
    original_description: str,
    original_tags: List[str],
    topic: str,
    script_text: str,
    timestamps_text: str = ""
) -> Dict:
    """
    Generate complete metadata package for YouTube upload.
    
    Args:
        original_title: Reference video title
        original_description: Reference video description
        original_tags: Reference video tags
        topic: Video topic
        script_text: Generated script text
        timestamps_text: Pre-formatted timestamps (from generate_timestamps.py)
    
    Returns:
        Dict with title, description (including timestamps), tags
    """
    # Extract hook from script
    sentences = re.split(r'(?<=[.!?])\s+', script_text)
    hook = ' '.join(sentences[:3])
    
    print("📝 Generating modified title...")
    title = generate_modified_title(original_title, topic, hook)
    
    print("📝 Generating description with timestamps...")
    description = generate_description(
        script_text, 
        topic, 
        original_description,
        timestamps_text=timestamps_text,
        include_timestamps=True
    )
    
    print("📝 Generating tags...")
    tags = extract_and_generate_tags(topic, original_tags, script_text)
    
    return {
        'title': title,
        'description': description,
        'tags': tags,
        'original_title': original_title,
        'topic': topic,
        'has_timestamps': bool(timestamps_text)
    }


if __name__ == "__main__":
    # Test
    test_metadata = generate_full_metadata(
        original_title="Silver Squeeze: The Hidden Truth Banks Don't Want You To Know",
        original_description="In this video I explain the silver market manipulation...",
        original_tags=["silver", "investing", "finance"],
        topic="silver market crash",
        script_text="Last night at 10:40 PM, someone dumped 2000 contracts. The price crashed 5%..."
    )
    print(json.dumps(test_metadata, indent=2))
