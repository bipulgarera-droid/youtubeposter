#!/usr/bin/env python3
"""
YouTube Niche Verifier - Flask Web Application
Main server for the content repurposing workflow.
"""

import os
import re
import json
import subprocess
import requests
from pathlib import Path
from flask import Flask, render_template, request, jsonify, send_from_directory, send_file, session, redirect
from dotenv import load_dotenv

# Load environment variables
# Load environment variables
load_dotenv()

# Allow OAuth over HTTP for local development
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

# Import execution modules
from execution.youtube_search import discover_videos
from execution.transcribe_video import transcribe_video
from execution.search_news import search_news
from execution.generate_script import generate_script
from execution.fetch_articles import fetch_multiple_articles
from execution.generate_video import build_video_from_chunks, check_ffmpeg
from execution.generate_ai_images import generate_all_images, generate_chunk_image, split_script_to_chunks
from execution.generate_narrative_script import generate_narrative_script, DEFAULT_BEATS
from execution.thumbnail_generator import (
    extract_video_id, download_thumbnail, dissect_thumbnail, 
    generate_thumbnail_prompt
)
from execution.title_generator import generate_title_options
from execution.keyword_research import research_keywords
from execution.youtube_video_info import get_video_details, get_multiple_video_details, format_duration
from execution.youtube_upload import (
    get_auth_url, handle_oauth_callback, is_authenticated, 
    upload_video, check_dependencies
)

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'dev-secret-key-change-in-prod')

# Paths
BASE_DIR = Path(__file__).parent
TMP_DIR = BASE_DIR / '.tmp'
SCREENSHOTS_DIR = TMP_DIR / 'screenshots'
DATA_FILE = BASE_DIR / 'data.json'

# Ensure directories exist
TMP_DIR.mkdir(exist_ok=True)
SCREENSHOTS_DIR.mkdir(exist_ok=True)

def load_persistent_data():
    """Load persistent data from JSON file."""
    if DATA_FILE.exists():
        with open(DATA_FILE, 'r') as f:
            return json.load(f)
    return {
        'projects': [],
        'current_project': None,
        'saved_videos': {}  # project_id -> [videos]
    }

def save_persistent_data(data):
    """Save persistent data to JSON file."""
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, indent=2)

# Load persistent data
persistent_data = load_persistent_data()

# In-memory state (session-based, resets on restart)
app_state = {
    'videos': [],
    'selected_videos': [],  # Changed to list for multi-select
    'transcript': None,
    'articles': [],
    'script': None,
    'screenshots': [],
    'claim_screenshots': []  # For Video Editor
}

# Try to restore claim_screenshots from manifest if they exist
try:
    manifest_path = TMP_DIR / 'screenshots' / 'claim_screenshots_manifest.json'
    if manifest_path.exists():
        with open(manifest_path, 'r') as f:
            saved_screenshots = json.load(f)
            if isinstance(saved_screenshots, list) and len(saved_screenshots) > 0:
                print(f"📸 Restoring {len(saved_screenshots)} screenshots from manifest")
                app_state['claim_screenshots'] = saved_screenshots
                app_state['screenshots'] = saved_screenshots  # Also populate legacy key
except Exception as e:
    print(f"⚠️ Failed to restore screenshots: {e}")

@app.route('/')
def index():
    """Render main dashboard."""
    return render_template('index.html')


# =============================================================================
# Health Check & Job Queue Endpoints (for Railway deployment)
# =============================================================================

@app.route('/health')
def health_check():
    """Health check endpoint for Railway/Docker."""
    return jsonify({
        'status': 'healthy',
        'service': 'youtube-niche-verifier',
        'version': '1.0.0'
    })


@app.route('/api/full-pipeline', methods=['POST'])
def api_full_pipeline():
    """
    Queue a full video generation pipeline.
    Expected JSON: { url: youtube_url, topic?: optional_topic }
    """
    try:
        from execution.job_queue import queue_full_pipeline
        
        data = request.json
        youtube_url = data.get('url')
        topic = data.get('topic')
        
        if not youtube_url:
            return jsonify({'error': 'Missing url parameter'}), 400
        
        job_id = queue_full_pipeline(youtube_url=youtube_url, topic=topic)
        
        return jsonify({
            'success': True,
            'job_id': job_id,
            'message': 'Pipeline job queued successfully'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/job-status/<job_id>')
def api_job_status(job_id):
    """Get status of a queued job."""
    try:
        from execution.job_queue import get_job_status
        
        status = get_job_status(job_id)
        if not status:
            return jsonify({'error': 'Job not found'}), 404
        
        return jsonify(status)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/extract-video-info', methods=['POST'])
def api_extract_video_info():
    """Extract video title and metadata from YouTube URL."""
    try:
        from execution.full_pipeline import extract_video_info
        
        data = request.json
        youtube_url = data.get('url')
        
        if not youtube_url:
            return jsonify({'error': 'Missing url parameter'}), 400
        
        info = extract_video_info(youtube_url)
        return jsonify(info)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/state')
def get_state():
    """Get current application state including persistent data."""
    return jsonify({
        **app_state,
        'claimScreenshots': app_state.get('screenshots', []),  # Frontend uses this key
        'projects': persistent_data['projects'],
        'current_project': persistent_data['current_project'],
        'saved_videos': persistent_data['saved_videos']
    })

@app.route('/api/discover', methods=['POST'])
def api_discover():
    """
    Discover YouTube videos matching criteria.
    Expected JSON: { query, multiplier, days, max_results }
    """
    data = request.json
    query = data.get('query', '')
    multiplier = float(data.get('multiplier', 1.0))
    days = int(data.get('days', 30))
    max_results = int(data.get('max_results', 50))
    min_views = int(data.get('min_views') or 0)
    min_duration_minutes = float(data.get('min_duration_minutes') or 0.0)
    
    if not query:
        return jsonify({'success': False, 'message': 'Query is required'}), 400
    
    result = discover_videos(
        query=query,
        min_multiplier=multiplier,
        days=days,
        max_results=max_results,
        min_views=min_views,
        min_duration_minutes=min_duration_minutes
    )
    
    if result['success']:
        app_state['videos'] = result['videos']
    
    return jsonify(result)

@app.route('/api/select-video', methods=['POST'])
def api_select_video():
    """
    Select a video for repurposing (legacy - single video).
    Expected JSON: { video_id }
    """
    data = request.json
    video_id = data.get('video_id')
    
    # Find video in list
    selected = None
    for video in app_state['videos']:
        if video['video_id'] == video_id:
            selected = video
            break
    
    if not selected:
        return jsonify({'success': False, 'message': 'Video not found'}), 404
    
    app_state['selected_videos'] = [selected]  # Put in list
    return jsonify({'success': True, 'video': selected})

@app.route('/api/transcribe', methods=['POST'])
def api_transcribe():
    """
    Transcribe ALL selected videos and combine transcripts.
    """
    if not app_state['selected_videos']:
        return jsonify({'success': False, 'message': 'No videos selected'}), 400
    
    all_transcripts = []
    successful_videos = []
    
    # Transcribe each selected video
    for i, video in enumerate(app_state['selected_videos']):
        video_id = video['video_id']
        video_title = video.get('title', 'Unknown')
        video_url = f"https://www.youtube.com/watch?v={video_id}"
        
        print(f"Transcribing video {i+1}/{len(app_state['selected_videos'])}: {video_title}")
        
        result = transcribe_video(video_url=video_url, keep_audio=True)
        
        if result['success']:
            # Add header for each video's transcript
            video_transcript = f"\n\n--- VIDEO: {video_title} ---\n\n{result['transcript']}"
            all_transcripts.append(video_transcript)
            successful_videos.append(video_title)
        else:
            print(f"Failed to transcribe {video_title}: {result.get('message', 'Unknown error')}")
    
    if not all_transcripts:
        return jsonify({'success': False, 'message': 'Failed to transcribe any videos'}), 500
    
    # Combine all transcripts
    combined_transcript = '\n'.join(all_transcripts)
    app_state['transcript'] = combined_transcript
    
    return jsonify({
        'success': True,
        'transcript': combined_transcript,
        'videos_transcribed': len(successful_videos),
        'video_titles': successful_videos,
        'message': f'Transcribed {len(successful_videos)} video(s)'
    })

@app.route('/api/transcribe-url', methods=['POST'])
def api_transcribe_url():
    """
    Transcribe a single video by URL (manual input).
    Expected JSON: { url: 'youtube_url' }
    """
    data = request.get_json()
    url = data.get('url', '').strip()
    
    if not url:
        return jsonify({'success': False, 'message': 'No URL provided'}), 400
    
    print(f"📝 Transcribing URL: {url}")
    
    result = transcribe_video(video_url=url, keep_audio=True)
    
    if result['success']:
        # Store the transcript in app state
        app_state['transcript'] = result['transcript']
        
        return jsonify({
            'success': True,
            'transcript': result['transcript'],
            'word_count': result.get('word_count', 0),
            'video_id': result.get('video_id'),
            'message': result.get('message', 'Transcribed successfully')
        })
    else:
        return jsonify({
            'success': False,
            'message': result.get('message', 'Failed to transcribe video')
        }), 400

@app.route('/api/search-news', methods=['POST'])
def api_search_news():
    """
    Search for related news articles.
    Expected JSON: { transcript, num_articles, channel_focus } or { topic, num_articles }
    """
    data = request.json
    num_articles = int(data.get('num_articles', 30))
    channel_focus = data.get('channel_focus', '')
    days_limit = int(data.get('days_limit', 7))  # Default 7 days
    
    # Get transcript from request or app state
    transcript = data.get('transcript') or app_state.get('transcript')
    topic = data.get('topic', '')
    
    # If no topic provided, extract from transcript
    if not topic and transcript:
        # Use first 200 characters of transcript as topic context
        topic = transcript[:500].replace('\n', ' ').strip()
    
    if not topic and not transcript:
        return jsonify({'success': False, 'message': 'No transcript or topic available'}), 400
    
    result = search_news(
        topic=topic,
        num_articles=num_articles,
        transcript=transcript,
        channel_focus=channel_focus,
        days_limit=days_limit
    )
    
    if result['success']:
        app_state['articles'] = result['articles']
    
    return jsonify(result)


@app.route('/api/suggest-topics', methods=['POST'])
def api_suggest_topics():
    """Generate 4 video topic suggestions based on transcript + articles + channel focus."""
    data = request.json
    transcript = data.get('transcript', '')
    articles = data.get('articles', [])
    channel_focus = data.get('channel_focus', '')
    
    if not transcript and not articles:
        return jsonify({'success': False, 'error': 'Need transcript or articles'}), 400
    
    # Build context for AI
    articles_summary = ""
    for i, article in enumerate(articles[:5]):
        articles_summary += f"\n{i+1}. {article.get('title', '')} - {article.get('snippet', '')[:150]}"
    
    prompt = f"""Based on this content, suggest exactly 4 compelling video topic titles.

TRANSCRIPT EXCERPT:
{transcript[:3000]}

NEWS ARTICLES:
{articles_summary}

CHANNEL FOCUS: {channel_focus if channel_focus else 'General news/analysis'}

REQUIREMENTS:
1. Each topic should be 8-15 words
2. Must be attention-grabbing for YouTube
3. Should incorporate the main theme AND the channel focus angle
4. Format the topic to work well for SEO (include key searchable terms)
5. Make each topic distinct - different angles on the same core story

Return ONLY 4 topics, one per line. No numbering, no explanations."""

    try:
        api_key = os.getenv('GEMINI_API_KEY')
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"
        
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.8,
                "maxOutputTokens": 500
            }
        }
        
        response = requests.post(url, json=payload, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            text = result.get('candidates', [{}])[0].get('content', {}).get('parts', [{}])[0].get('text', '')
            
            # Parse topics (one per line)
            topics = [line.strip() for line in text.strip().split('\n') if line.strip() and len(line.strip()) > 10][:4]
            
            if topics:
                return jsonify({'success': True, 'topics': topics})
            else:
                return jsonify({'success': False, 'error': 'No topics generated'}), 500
        else:
            return jsonify({'success': False, 'error': f'API error: {response.status_code}'}), 500
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/generate-script', methods=['POST'])
def api_generate_script():
    """
    Generate the video script.
    Fetches full article content first, then generates script with new information.
    """
    data = request.json
    
    # Get transcript and articles from request or state
    transcript = data.get('transcript') or app_state.get('transcript')
    articles = data.get('articles') or app_state.get('articles', [])
    word_count = data.get('word_count', 4000)
    channel_focus = data.get('channel_focus', '')
    script_mode = data.get('script_mode', 'original')
    selected_topic = data.get('selected_topic', '')  # Topic selected from UI
    reference_video_id = data.get('reference_video_id')
    
    if not articles:
        return jsonify({'success': False, 'message': 'No articles found. Search for news first.'}), 400
    
    # Validation based on mode
    if script_mode == 'transcript_refined' and not transcript:
        return jsonify({'success': False, 'message': 'Transcript required for Transcript-Refined mode. Please Transcribe a video first.'}), 400
    
    # For news_based and original modes, we need either selected_topic or will derive from articles
    if script_mode in ['news_based', 'original'] and not selected_topic and not transcript:
        # If no topic selected and no transcript, use first article title as topic context
        if articles:
            selected_topic = articles[0].get('title', 'Breaking News Update')
    
    # Step 1: Fetch full content from article URLs (Top 30)
    print(f"Fetching content from {len(articles)} articles...")
    enriched_articles = fetch_multiple_articles(articles[:30], max_articles=30)
    
    # Extract topic: prioritize selected_topic, then transcript
    topic = selected_topic or ''
    if not topic and transcript:
        topic = transcript[:300].replace('\n', ' ').strip()
    
    # Step 2: Generate script with enriched articles
    result = generate_script(
        topic=topic,
        articles=enriched_articles,
        transcript=transcript if script_mode == 'transcript_refined' else None,  # Only pass transcript for transcript_refined mode
        word_count=word_count,
        channel_focus=channel_focus,
        script_mode=script_mode
    )
    
    if result['success']:
        app_state['script'] = result['script']
    
    return jsonify(result)


# ============== NARRATIVE ENGINE SCRIPT GENERATION ==============

@app.route('/api/narrative-beats', methods=['GET'])
def api_get_narrative_beats():
    """Get the default narrative beat structure."""
    return jsonify({
        'success': True,
        'beats': DEFAULT_BEATS,
        'total_words': sum(b['word_target'] for b in DEFAULT_BEATS)
    })


@app.route('/api/generate-narrative-script', methods=['POST'])
def api_generate_narrative_script():
    """
    Generate script using narrative engine (beat-based structure).
    
    Expected JSON:
    {
        topic: str,
        target_minutes: int (default: 15),
        research: str (optional - combines with stored transcript/articles)
    }
    """
    data = request.json
    topic = data.get('topic', '').strip()
    target_minutes = data.get('target_minutes', 15)
    custom_research = data.get('research', '')
    
    if not topic:
        return jsonify({'success': False, 'message': 'Topic is required'}), 400
    
    # Build research data from multiple sources
    research_parts = []
    
    # Get data from request or state
    transcript = data.get('transcript') or app_state.get('transcript')
    articles = data.get('articles') or app_state.get('articles')
    
    # Debug: show what we have
    print(f"📊 Available data: transcript={bool(transcript)}, articles={bool(articles)} ({len(articles) if articles else 0} items)")
    
    # Add stored transcript (FULL transcript)
    if transcript:
        print(f"📜 Transcript: {len(transcript)} chars")
        research_parts.append(f"=== REFERENCE TRANSCRIPT ===\n{transcript}")
    
    # Fetch FULL article content via Camofoux (like old script flow)
    if articles:
        # If articles came from request, they might just be dicts without full content
        # Check if we need to fetch content
        needs_fetch = any(not a.get('full_content') for a in articles[:20])
        
        if needs_fetch:
            print(f"📰 Fetching full content from {len(articles)} articles via Camofoux...")
            enriched_articles = fetch_multiple_articles(articles[:20], max_articles=20)
        else:
            enriched_articles = articles
        
        articles_text = []
        for i, article in enumerate(enriched_articles[:20]):
            title = article.get('title', 'Untitled')
            # Get full scraped content, fallback to snippet
            content = article.get('full_content') or article.get('content') or article.get('snippet', '')
            if content:
                articles_text.append(f"ARTICLE {i+1}: {title}\n{content[:3000]}")  # 3000 chars per article
        
        if articles_text:
            print(f"📰 Using {len(articles_text)} enriched articles")
            research_parts.append(f"=== NEWS ARTICLES ===\n" + "\n\n".join(articles_text))
    
    # Add custom research
    if custom_research:
        research_parts.append(f"=== ADDITIONAL RESEARCH ===\n{custom_research}")
    
    combined_research = "\n\n".join(research_parts) if research_parts else f"Topic: {topic}"
    
    print(f"🎬 Generating narrative script: {topic} ({target_minutes} min)")
    print(f"📚 Research sources: {len(research_parts)} parts, ~{len(combined_research)} chars")
    
    try:
        result = generate_narrative_script(
            research_data=combined_research,
            topic=topic,
            target_minutes=target_minutes
        )
        
        if result['success']:
            # Store in app_state for use in other workflows
            app_state['narrative_script'] = result
            
            # Also store as regular script for compatibility
            app_state['script'] = {
                'raw_text': result['full_script'],
                'word_count': result['total_words'],
                'narrative_beats': result['beats']
            }
            
            # Store chunks for AI image generation
            app_state['script_chunks'] = result['all_chunks']
            
            return jsonify({
                'success': True,
                'topic': result['topic'],
                'total_words': result['total_words'],
                'estimated_minutes': result['estimated_minutes'],
                'beat_count': len(result['beats']),
                'chunk_count': result['total_chunks'],
                'beats': result['beats'],
                'full_script': result['full_script']
            })
        else:
            return jsonify({'success': False, 'message': 'Failed to generate script'})
            
    except Exception as e:
        print(f"❌ Error generating narrative script: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/regenerate-beat', methods=['POST'])
def api_regenerate_beat():
    """
    Regenerate a single beat of the narrative script.
    
    Expected JSON:
    {
        beat_id: str,
        topic: str
    }
    """
    from execution.generate_narrative_script import generate_beat, split_into_chunks
    
    data = request.json
    beat_id = data.get('beat_id')
    topic = data.get('topic', '')
    
    if not beat_id:
        return jsonify({'success': False, 'message': 'beat_id is required'}), 400
    
    # Find the beat definition
    beat_def = None
    for b in DEFAULT_BEATS:
        if b['id'] == beat_id:
            beat_def = b
            break
    
    if not beat_def:
        return jsonify({'success': False, 'message': f'Unknown beat: {beat_id}'}), 400
    
    # Get previous beats for context
    narrative_script = app_state.get('narrative_script', {})
    previous_beats = []
    for b in narrative_script.get('beats', []):
        if b['id'] == beat_id:
            break
        previous_beats.append(b)
    
    # Build research
    research = ""
    if app_state.get('transcript'):
        research += f"TRANSCRIPT:\n{app_state['transcript'][:5000]}\n\n"
    
    try:
        result = generate_beat(beat_def, research, previous_beats, topic)
        result['chunks'] = split_into_chunks(result['text'], max_words=12)
        result['chunk_count'] = len(result['chunks'])
        
        # Update stored script
        if narrative_script.get('beats'):
            for i, b in enumerate(narrative_script['beats']):
                if b['id'] == beat_id:
                    narrative_script['beats'][i] = result
                    break
            
            # Recombine full script
            narrative_script['full_script'] = "\n\n".join([
                b['text'] for b in narrative_script['beats'] if b.get('text')
            ])
            narrative_script['total_words'] = sum(
                b.get('word_count', 0) for b in narrative_script['beats']
            )
            app_state['narrative_script'] = narrative_script
        
        return jsonify({
            'success': True,
            'beat': result
        })
        
    except Exception as e:
        print(f"❌ Error regenerating beat: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/capture-screenshots', methods=['POST'])
def api_capture_screenshots():
    """
    Capture screenshots with highlights.
    Extracts URLs from the script's raw_text.
    """
    import re
    
    if not app_state['script']:
        return jsonify({'success': False, 'message': 'No script generated. Generate script first.'}), 400
    
    # Extract URLs from raw_text (new format: URLs on their own lines)
    raw_text = app_state['script'].get('raw_text', '')
    
    # Find all URLs - they appear on their own lines
    url_pattern = r'^(https?://[^\s]+)$'
    found_urls = re.findall(url_pattern, raw_text, re.MULTILINE)
    
    # Deduplicate while preserving order
    seen = set()
    unique_urls = []
    for url in found_urls:
        if url not in seen:
            seen.add(url)
            unique_urls.append(url)
    
    # Domain-based diversity: Max 2 URLs per domain to avoid content overlap
    from urllib.parse import urlparse
    domain_count = {}
    diverse_urls = []
    for url in unique_urls:
        try:
            domain = urlparse(url).netloc.replace('www.', '')
            if domain_count.get(domain, 0) < 2:  # Max 2 per domain
                diverse_urls.append(url)
                domain_count[domain] = domain_count.get(domain, 0) + 1
        except:
            diverse_urls.append(url)  # Keep URL if parsing fails
    
    print(f"Found {len(unique_urls)} unique URLs, {len(diverse_urls)} after domain diversity filter")
    
    # Create urls_with_highlights structure (up to 35 unique URLs for comprehensive coverage)
    urls_with_highlights = [{'url': url, 'highlight_text': ''} for url in diverse_urls[:35]]
    
    if not urls_with_highlights:
        return jsonify({'success': False, 'message': 'No URLs found in script. Make sure URLs are on their own lines.'}), 400
    
    # Write URLs to temp file
    urls_file = TMP_DIR / 'urls_to_capture.json'
    with open(urls_file, 'w') as f:
        json.dump(urls_with_highlights, f)
    
    # Run Node.js screenshot script (STEALTH MODE)
    try:
        result = subprocess.run(
            ['node', 'execution/capture_screenshots_stealth.js', '--urls', str(urls_file)],
            capture_output=True,
            text=True,
            cwd=str(BASE_DIR),
            timeout=600  # Increased to 10 minutes for stealth delays
        )
        
        if result.returncode != 0:
            print(f"Screenshot script error: {result.stderr}")
            return jsonify({
                'success': False,
                'message': f'Screenshot capture failed: {result.stderr}'
            }), 500
        
        # Parse output
        output = result.stdout
        
        # Look for JSON between markers first (new script format)
        import re
        json_match = re.search(r'__JSON_START__\s*(.*)\s*__JSON_END__', output, re.DOTALL)
        
        if json_match:
            try:
                screenshots_data = json.loads(json_match.group(1))
            except json.JSONDecodeError as e:
                print(f"JSON Parse Error: {e}")
                print(f"Raw output: {output}")
                return jsonify({'success': False, 'message': 'Failed to parse screenshot results'}), 500
        else:
            # Fallback to finding first array
            json_start = output.find('[')
            json_end = output.rfind(']') + 1
            if json_start >= 0 and json_end > json_start:
                try:
                    screenshots_data = json.loads(output[json_start:json_end])
                except json.JSONDecodeError:
                    return jsonify({'success': False, 'message': 'Failed to parse screenshot output'}), 500
            else:
                return jsonify({'success': False, 'message': 'No valid output from screenshot script'}), 500

        # Update state
        app_state['screenshots'] = screenshots_data
        
        # Save manifest
        manifest_path = SCREENSHOTS_DIR / 'screenshots_manifest.json'
        with open(manifest_path, 'w') as f:
            json.dump(screenshots_data, f, indent=2)
            
        return jsonify({
            'success': True,
            'screenshots': screenshots_data,
            'count': len(screenshots_data)
        })
        
    except subprocess.TimeoutExpired:
        return jsonify({'success': False, 'message': 'Screenshot capture timed out'}), 504
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/screenshots/<path:filename>')
def serve_screenshot(filename):
    """Serve captured screenshots from .tmp directory"""
    return send_from_directory(SCREENSHOTS_DIR, filename)


# AI Image Generation Directory
AI_IMAGES_DIR = BASE_DIR / '.tmp' / 'ai_images'
AI_IMAGES_DIR.mkdir(parents=True, exist_ok=True)

@app.route('/api/generate-ai-images', methods=['POST'])
def api_generate_ai_images():
    """
    Generate AI images for all chunks in the script.
    Uses Gemini 2.5 Flash Image with 16:9 YouTube dimensions.
    """
    data = request.json or {}
    script = data.get('script') or app_state.get('script', {}).get('raw_text', '')
    
    if not script:
        return jsonify({'success': False, 'message': 'No script available'}), 400
    
    print("\n" + "="*60)
    print("AI IMAGE GENERATION")
    print("="*60)
    
    # Get unique folder name based on timestamp
    from datetime import datetime
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_dir = AI_IMAGES_DIR / f"batch_{timestamp}"
    
    try:
        result = generate_all_images(script, str(output_dir))
        
        if result['success'] or result['successful'] > 0:
            # Format chunks for frontend
            chunks = []
            for chunk in result.get('chunks', []):
                if chunk.get('success'):
                    # Convert path to URL
                    # Path is absolute, make relative to AI_IMAGES_DIR
                    try:
                        rel_path = Path(chunk['path']).relative_to(AI_IMAGES_DIR)
                    except ValueError:
                        # Fallback if somehow not in AI_IMAGES_DIR
                        rel_path = Path(chunk['path']).name
                        
                    chunks.append({
                        'index': chunk['index'],
                        'text': chunk['chunk_text'],
                        'image_url': f'/api/ai-images/{rel_path}',
                        'metaphor': chunk.get('metaphor', ''),
                        'path': chunk['path']
                    })
            
            # Store in app state
            app_state['ai_image_chunks'] = chunks
            
            # CRITICAL: Save the script to the batch folder for recovery after restart
            try:
                script_file = output_dir / 'script.txt'
                script_file.write_text(script)
                print(f"💾 Saved script to {script_file}")
            except Exception as e:
                print(f"⚠️ Failed to save script: {e}")
            
            return jsonify({
                'success': True,
                'chunks': chunks,
                'total': result['total_chunks'],
                'generated': result['successful'],
                'output_dir': str(output_dir)
            })
        else:
            return jsonify({'success': False, 'message': 'Failed to generate images'}), 500
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/regenerate-chunk-image', methods=['POST'])
def api_regenerate_chunk_image():
    """
    Regenerate a single chunk's image.
    """
    data = request.json or {}
    chunk_text = data.get('text', '')
    chunk_index = data.get('index', 0)
    
    if not chunk_text:
        return jsonify({'success': False, 'message': 'No chunk text provided'}), 400
    
    from datetime import datetime
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_path = AI_IMAGES_DIR / f"regen_{chunk_index}_{timestamp}.png"
    
    try:
        result = generate_chunk_image(chunk_text, str(output_path), chunk_index)
        
        if result['success']:
            try:
                rel_path = output_path.relative_to(AI_IMAGES_DIR)
            except ValueError:
                rel_path = output_path.name
                
            return jsonify({
                'success': True,
                'image_url': f'/api/ai-images/{rel_path}',
                'metaphor': result.get('metaphor', ''),
                'path': str(output_path)
            })
        else:
            return jsonify({'success': False, 'message': result.get('error', 'Generation failed')}), 500
            
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/ai-images/<path:filename>')
def serve_ai_image(filename):
    """Serve AI-generated images. Handles potential double nested paths."""
    # Fix for double ai_images path issue
    if filename.startswith('ai_images/'):
        filename = filename.replace('ai_images/', '', 1)
    return send_from_directory(AI_IMAGES_DIR, filename)


@app.route('/api/claim-screenshots', methods=['POST'])
def api_claim_screenshots():
    """
    Claim-Based Screenshot Generation.
    Splits script into chunks, searches for each claim, captures screenshots.
    """
    from execution.claim_screenshots import generate_claim_screenshots_data, chunk_script
    
    data = request.json
    script = data.get('script') or app_state.get('script', {}).get('raw_text', '')
    
    if not script:
        return jsonify({'success': False, 'message': 'No script available'}), 400
    
    print("\n" + "="*60)
    print("CLAIM-BASED SCREENSHOT GENERATION")
    print("="*60)
    
    # Step 1: Generate claim data (chunks + search results)
    claim_data = generate_claim_screenshots_data(script)
    
    if not claim_data['success']:
        return jsonify({'success': False, 'message': 'Failed to process script'}), 500
    
    # Get video name from selected videos or use timestamp
    video_name = "video"
    if app_state.get('selected_videos'):
        # Use first selected video's title (sanitized)
        first_video = app_state['selected_videos'][0] if isinstance(app_state['selected_videos'], list) else app_state['selected_videos']
        if isinstance(first_video, dict) and first_video.get('title'):
            video_name = re.sub(r'[^\w\s-]', '', first_video['title'])[:30].strip().replace(' ', '_').lower()
    if not video_name or video_name == "video":
        from datetime import datetime
        video_name = f"vid_{datetime.now().strftime('%Y%m%d_%H%M')}"
    
    # Step 2: Write data for Node.js script (include video_name)
    data_file = TMP_DIR / 'claim_screenshots_data.json'
    screenshot_data_with_name = {
        'video_name': video_name,
        'chunks': claim_data['screenshots_data']
    }
    with open(data_file, 'w') as f:
        json.dump(screenshot_data_with_name, f)
    
    # Step 3: Run screenshot capture
    try:
        result = subprocess.run(
            ['node', 'execution/capture_claim_screenshots.js', '--data', str(data_file)],
            capture_output=True,
            text=True,
            cwd=str(BASE_DIR),
            timeout=1800  # 30 minutes for many screenshots
        )
        
        if result.returncode != 0:
            print(f"Screenshot script error: {result.stderr}")
            return jsonify({'success': False, 'message': f'Screenshot capture failed'}), 500
        
        # Parse output
        output = result.stdout
        json_match = re.search(r'__JSON_START__\s*(.*)\s*__JSON_END__', output, re.DOTALL)
        
        if json_match:
            screenshots_data = json.loads(json_match.group(1))
        else:
            return jsonify({'success': False, 'message': 'No valid output from screenshot script'}), 500
        
        # Merge chunk text with screenshot results
        for ss in screenshots_data:
            chunk_index = ss.get('chunk_index')
            for item in claim_data['screenshots_data']:
                if item['chunk_index'] == chunk_index:
                    ss['chunk_text'] = item['chunk_text']
                    ss['claim'] = item['claim']
                    break
        
        # Update state
        app_state['claim_screenshots'] = screenshots_data
        
        # Save manifest
        manifest_path = SCREENSHOTS_DIR / 'claim_screenshots_manifest.json'
        with open(manifest_path, 'w') as f:
            json.dump(screenshots_data, f, indent=2)
        
        successful = len([s for s in screenshots_data if s.get('success')])
        
        return jsonify({
            'success': True,
            'screenshots': screenshots_data,
            'total_chunks': claim_data['total_chunks'],
            'successful': successful,
            'message': f'Captured {successful} of {claim_data["total_chunks"]} screenshots'
        })
        
    except subprocess.TimeoutExpired:
        return jsonify({'success': False, 'message': 'Screenshot capture timed out'}), 504
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/download-screenshots')
def download_screenshots():
    """Download all screenshots as a ZIP file"""
    import zipfile
    from io import BytesIO
    
    # Get all PNG files in screenshots directory
    screenshots = list(SCREENSHOTS_DIR.glob('*.png'))
    
    if not screenshots:
        return jsonify({'success': False, 'message': 'No screenshots to download'}), 404
    
    # Create ZIP in memory
    memory_file = BytesIO()
    with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
        for filepath in screenshots:
            zf.write(filepath, filepath.name)
    
    memory_file.seek(0)
    
    return send_file(
        memory_file,
        mimetype='application/zip',
        as_attachment=True,
        download_name='screenshots.zip'
    )

@app.route('/api/generate-audio', methods=['POST'])
def api_generate_audio():
    """Generate audio for a script section using Google Cloud TTS Chirp 3 HD."""
    import requests
    import base64
    
    data = request.json
    text = data.get('text', '')
    section_index = data.get('section_index', 0)
    
    if not text:
        return jsonify({'success': False, 'error': 'No text provided'}), 400
    
    # Clean text for TTS (remove URLs, special characters)
    import re
    clean_text = re.sub(r'https?://\S+', '', text)  # Remove URLs
    clean_text = re.sub(r'\n+', ' ', clean_text)    # Replace newlines with spaces
    clean_text = clean_text.strip()
    
    if not clean_text:
        return jsonify({'success': False, 'error': 'No speakable text after cleaning'}), 400
    
    gemini_api_key = os.getenv('GEMINI_API_KEY')
    if not gemini_api_key:
        return jsonify({'success': False, 'error': 'GEMINI_API_KEY not configured'}), 500
    
    # Google Cloud TTS API endpoint
    tts_url = f"https://texttospeech.googleapis.com/v1beta1/text:synthesize?key={gemini_api_key}"
    
    # Request body for Chirp 3 HD with Charon voice
    tts_payload = {
        "audioConfig": {
            "audioEncoding": "LINEAR16",
            "pitch": 0,
            "speakingRate": 1
        },
        "input": {
            "text": clean_text
        },
        "voice": {
            "languageCode": "en-US",
            "name": "en-US-Chirp3-HD-Charon"
        }
    }
    
    try:
        response = requests.post(
            tts_url,
            headers={'Content-Type': 'application/json'},
            json=tts_payload,
            timeout=60
        )
        
        if response.status_code != 200:
            error_msg = response.json().get('error', {}).get('message', 'Unknown error')
            return jsonify({'success': False, 'error': f'TTS API error: {error_msg}'}), 500
        
        result = response.json()
        audio_content = result.get('audioContent', '')
        
        if not audio_content:
            return jsonify({'success': False, 'error': 'No audio content returned'}), 500
        
        # Decode base64 audio and save to file
        audio_bytes = base64.b64decode(audio_content)
        
        # Ensure audio directory exists
        audio_dir = TMP_DIR / 'audio'
        audio_dir.mkdir(exist_ok=True)
        
        # Save audio file
        filename = f"section_{section_index}_{int(__import__('time').time())}.wav"
        filepath = audio_dir / filename
        
        with open(filepath, 'wb') as f:
            f.write(audio_bytes)
        
        return jsonify({
            'success': True,
            'filename': filename,
            'path': f'/api/audio/{filename}',
            'duration_estimate': len(clean_text.split()) / 2.5  # Rough estimate: 150 wpm
        })
        
    except requests.exceptions.Timeout:
        return jsonify({'success': False, 'error': 'TTS API timeout'}), 504
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/audio/<path:filename>')
def serve_audio(filename):
    """Serve generated audio files."""
    audio_dir = TMP_DIR / 'audio'
    return send_from_directory(audio_dir, filename, mimetype='audio/wav')


@app.route('/api/regenerate-chunk-audio', methods=['POST'])
def api_regenerate_chunk_audio():
    """Regenerate audio for a specific chunk. Overwrites existing audio file."""
    import requests
    import base64
    
    data = request.json
    text = data.get('text', '')
    chunk_index = data.get('chunk_index', 0)
    
    if not text:
        return jsonify({'success': False, 'error': 'No text provided'}), 400
    
    # Clean text for TTS
    import re
    clean_text = re.sub(r'https?://\S+', '', text)
    clean_text = re.sub(r'\n+', ' ', clean_text)
    clean_text = clean_text.strip()
    
    if not clean_text:
        return jsonify({'success': False, 'error': 'No speakable text after cleaning'}), 400
    
    gemini_api_key = os.getenv('GEMINI_API_KEY')
    if not gemini_api_key:
        return jsonify({'success': False, 'error': 'GEMINI_API_KEY not configured'}), 500
    
    # Google Cloud TTS API endpoint
    tts_url = f"https://texttospeech.googleapis.com/v1beta1/text:synthesize?key={gemini_api_key}"
    
    # Request body for Chirp 3 HD with Charon voice
    tts_payload = {
        "audioConfig": {
            "audioEncoding": "LINEAR16",
            "pitch": 0,
            "speakingRate": 1
        },
        "input": {
            "text": clean_text
        },
        "voice": {
            "languageCode": "en-US",
            "name": "en-US-Chirp3-HD-Charon"
        }
    }
    
    try:
        response = requests.post(
            tts_url,
            headers={'Content-Type': 'application/json'},
            json=tts_payload,
            timeout=60
        )
        
        if response.status_code != 200:
            error_msg = response.json().get('error', {}).get('message', 'Unknown error')
            return jsonify({'success': False, 'error': f'TTS API error: {error_msg}'}), 500
        
        result = response.json()
        audio_content = result.get('audioContent', '')
        
        if not audio_content:
            return jsonify({'success': False, 'error': 'No audio content returned'}), 500
        
        # Decode base64 audio
        audio_bytes = base64.b64decode(audio_content)
        
        # Ensure audio directory exists
        audio_dir = TMP_DIR / 'audio'
        audio_dir.mkdir(exist_ok=True)
        
        # Delete any existing audio for this chunk
        for pattern in [f"chunk_{chunk_index}_*.wav", f"chunk_{chunk_index}_*.mp3", f"section_{chunk_index}_*.wav"]:
            for old_file in audio_dir.glob(pattern):
                try:
                    old_file.unlink()
                    print(f"🗑️ Deleted old audio: {old_file.name}")
                except:
                    pass
        
        # Save with fixed filename (chunk_X.wav) so new audio overwrites concept
        filename = f"chunk_{chunk_index}.wav"
        filepath = audio_dir / filename
        
        with open(filepath, 'wb') as f:
            f.write(audio_bytes)
        
        print(f"✅ Generated audio for chunk {chunk_index}: {filename}")
        
        return jsonify({
            'success': True,
            'chunk_index': chunk_index,
            'filename': filename,
            'audio_url': f'/api/audio/{filename}',
            'duration_estimate': len(clean_text.split()) / 2.5
        })
        
    except requests.exceptions.Timeout:
        return jsonify({'success': False, 'error': 'TTS API timeout'}), 504
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================
# VIDEO GENERATION ENDPOINTS
# ============================================

# Helper for AI image recovery
def recover_latest_ai_batch(script_text=None):
    """Scan AI_IMAGES_DIR for the latest batch and reconstruct chunks."""
    try:
        if not AI_IMAGES_DIR.exists():
            return []
            
        batch_dirs = sorted([d for d in AI_IMAGES_DIR.iterdir() if d.is_dir() and d.name.startswith('batch_')], key=lambda d: d.stat().st_mtime, reverse=True)
        if not batch_dirs:
            return []
            
        latest_batch = batch_dirs[0]
        print(f"♻️  Scanning images from {latest_batch.name}")
        
        recovered_chunks = []
        image_files = sorted(list(latest_batch.glob('*.png')))
        
        # Try to match script text
        script_chunks = []
        
        # Auto-load script from batch folder if not provided (recovery after restart)
        script_file = latest_batch / 'script.txt'
        if not script_text:
            if script_file.exists():
                print(f"📄 Auto-loading script from {script_file}")
                try:
                    script_text = script_file.read_text()
                except Exception as e:
                    print(f"Failed to read script.txt: {e}")
            else:
                print(f"⚠️ No script.txt found in {latest_batch.name}")
        else:
            # Script provided from frontend - save it for future use if not already saved
            if not script_file.exists():
                try:
                    script_file.write_text(script_text)
                    print(f"💾 Saved script to {script_file} for future recovery")
                except Exception as e:
                    print(f"⚠️ Failed to save script: {e}")

        if script_text:
            print(f"✅ Script text received: {len(script_text)} chars, first 100: {script_text[:100]}...")
            try:
                from execution.generate_ai_images import split_script_to_chunks
                script_chunks = split_script_to_chunks(script_text)
                print(f"✅ Split into {len(script_chunks)} chunks")
                if script_chunks:
                    print(f"   First chunk: {script_chunks[0][:60]}...")
            except Exception as e:
                print(f"Failed to split script: {e}")
        else:
            print("⚠️ No script_text provided or loaded. Chunks will default to 'Chunk X' labels.")
        
        for img in image_files:
            try:
                # filename format: chunk_001.png
                parts = img.stem.split('_')
                if len(parts) >= 2 and parts[0] == 'chunk':
                    idx = int(parts[1])  # 0-based index (chunk_000.png = index 0)
                    
                    # Create relative path properly
                    rel_path = img.relative_to(AI_IMAGES_DIR)
                    
                    # Try to get text - idx is 0-based so use directly
                    text = f"Chunk {idx + 1}"  # Display as 1-based for users
                    if script_chunks and idx < len(script_chunks):
                        text = script_chunks[idx]
                    
                    recovered_chunks.append({
                        'index': idx,
                        'chunk_text': text, 
                        'text': text,
                        'image_url': f"/api/ai-images/{rel_path}",
                        'metaphor': 'Recovered from session',
                        'path': str(img),
                        'success': True
                    })
            except Exception as e:
                continue
                
        if recovered_chunks:
            recovered_chunks.sort(key=lambda x: x['index'])
            
        return recovered_chunks
    except Exception as e:
        print(f"⚠️ Recovery helper failed: {e}")
        return []

@app.route('/api/video-chunks', methods=['GET'])
def api_get_video_chunks():
    """Get all chunks with their audio and screenshot status.
    Prioritizes AI-generated images over claim screenshots.
    """
    
    # Check for AI-generated image chunks first
    ai_chunks = app_state.get('ai_image_chunks', [])
    claim_chunks = app_state.get('claim_screenshots', [])
    
    recovered = False
    
    # Auto-recovery: If no chunks in memory, look for latest batch logic
    if not ai_chunks:
        script = app_state.get('script')
        text = script.get('raw_text') if script else None
        
        recovered_list = recover_latest_ai_batch(text)
        if recovered_list:
            app_state['ai_image_chunks'] = recovered_list
            ai_chunks = recovered_list
            print(f"✅ Recovered {len(recovered_list)} chunks")
            recovered = True

    # Decide which source to use
    if ai_chunks:
        # Use AI-generated images
        source_chunks = ai_chunks
        use_ai_images = True
        print(f"📎 Loading {len(ai_chunks)} AI-generated image chunks")
    elif claim_chunks:
        # Fallback to claim screenshots
        source_chunks = claim_chunks
        use_ai_images = False
        print(f"📎 Loading {len(claim_chunks)} claim screenshot chunks")
    else:
        return jsonify({
            'success': True,
            'chunks': [],
            'total': 0,
            'ready_count': 0
        })
    
    audio_dir = TMP_DIR / 'audio'
    
    video_chunks = []
    for i, chunk in enumerate(source_chunks):
        if use_ai_images:
            # AI image chunk structure
            chunk_data = {
                'id': i,
                'chunk_index': chunk.get('index', i),
                'text': chunk.get('text', '')[:100],
                'full_text': chunk.get('text', ''),
                'has_screenshot': True,
                'screenshot_path': chunk.get('path', ''),
                'screenshot_url': chunk.get('image_url', ''),
                'has_audio': False,
                'audio_path': '',
                'audio_url': None,
                'is_ai_image': True,
                'metaphor': chunk.get('metaphor', '')
            }
        else:
            # Claim screenshot chunk structure  
            chunk_data = {
                'id': i,
                'chunk_index': chunk.get('chunk_index', i),
                'text': chunk.get('chunk_text', chunk.get('claim', ''))[:100],
                'full_text': chunk.get('chunk_text', chunk.get('claim', '')),
                'has_screenshot': chunk.get('success', False),
                'screenshot_path': chunk.get('filepath', chunk.get('local_path', '')),
                'screenshot_url': f"/api/screenshots/{Path(chunk.get('filepath', chunk.get('local_path', ''))).name}" if chunk.get('filepath') or chunk.get('local_path') else None,
                'has_audio': False,
                'audio_path': '',
                'audio_url': None,
                'is_ai_image': False
            }
        
        # Check for audio file - support both new format (chunk_X.wav) and old format (chunk_X_timestamp.wav)
        audio_patterns = [f"chunk_{i}.wav", f"chunk_{i}.mp3", f"chunk_{i}_*.wav", f"chunk_{i}_*.mp3", f"section_{i}_*.wav"]
        for pattern in audio_patterns:
            audio_files = list(audio_dir.glob(pattern))
            if audio_files:
                latest = max(audio_files, key=lambda p: p.stat().st_mtime)
                chunk_data['has_audio'] = True
                chunk_data['audio_path'] = str(latest)
                chunk_data['audio_url'] = f"/api/audio/{latest.name}"
                break
        
        video_chunks.append(chunk_data)
    
    return jsonify({
        'success': True,
        'chunks': video_chunks,
        'total': len(video_chunks),
        'ready_count': len([c for c in video_chunks if c['has_audio']]),
        'source': 'ai_images' if use_ai_images else 'claim_screenshots',
        'recovered': recovered
    })

@app.route('/api/force-load-ai-images', methods=['POST'])
def api_force_load_ai_images():
    """Manually force load latest AI images from disk."""
    print("Force loading AI images...")
    
    # Try to get text from request first
    data = request.json or {}
    text = data.get('script_text')
    
    if not text:
        # Fallback to app_state
        script = app_state.get('script')
        text = script.get('raw_text') if script else None
    
    recovered_list = recover_latest_ai_batch(text)
    
    if recovered_list:
        app_state['ai_image_chunks'] = recovered_list
        return jsonify({
            'success': True,
            'count': len(recovered_list),
            'message': f"Loaded {len(recovered_list)} images from latest batch"
        })
    else:
        return jsonify({
            'success': False,
            'message': "No AI image batches found"
        }), 404


@app.route('/api/generate-chunk-audio', methods=['POST'])
def api_generate_chunk_audio():
    """Generate audio for a specific chunk using TTS."""
    import requests
    import base64
    import time
    
    data = request.json
    chunk_index = data.get('chunk_index', 0)
    text = data.get('text', '')
    
    if not text:
        return jsonify({'success': False, 'error': 'No text provided'}), 400
    
    # Get Google Cloud API key
    api_key = os.getenv('GOOGLE_CLOUD_API_KEY') or os.getenv('GEMINI_API_KEY', '')
    if not api_key:
        return jsonify({'success': False, 'error': 'API key not set (need GOOGLE_CLOUD_API_KEY or GEMINI_API_KEY)'}), 500
    
    # Clean text for TTS
    clean_text = re.sub(r'\[.*?\]', '', text)  # Remove source references
    clean_text = re.sub(r'https?://\S+', '', clean_text)  # Remove URLs
    clean_text = clean_text.strip()
    
    if not clean_text:
        return jsonify({'success': False, 'error': 'No speakable text after cleaning'}), 400
    
    # Call Google Cloud TTS v1beta1 API with Chirp 3 HD voice
    tts_url = f"https://texttospeech.googleapis.com/v1beta1/text:synthesize?key={api_key}"
    
    payload = {
        "audioConfig": {
            "audioEncoding": "LINEAR16",
            "pitch": 0,
            "speakingRate": 1
        },
        "input": {"text": clean_text},
        "voice": {"languageCode": "en-US", "name": "en-US-Chirp3-HD-Charon"}
    }
    
    try:
        response = requests.post(tts_url, json=payload, timeout=60)
        
        if response.status_code != 200:
            error_msg = response.json().get('error', {}).get('message', 'Unknown error')
            return jsonify({'success': False, 'error': f'TTS API error: {error_msg}'}), 500
        
        result = response.json()
        audio_content = result.get('audioContent', '')
        
        if not audio_content:
            return jsonify({'success': False, 'error': 'No audio content returned'}), 500
        
        # Decode and save
        audio_bytes = base64.b64decode(audio_content)
        audio_dir = TMP_DIR / 'audio'
        audio_dir.mkdir(exist_ok=True)
        
        filename = f"chunk_{chunk_index}_{int(time.time())}.wav"
        filepath = audio_dir / filename
        
        with open(filepath, 'wb') as f:
            f.write(audio_bytes)
        
        return jsonify({
            'success': True,
            'chunk_index': chunk_index,
            'filename': filename,
            'audio_url': f'/api/audio/{filename}',
            'path': str(filepath)
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/generate-all-audio', methods=['POST'])
def api_generate_all_audio():
    """Generate audio for all chunks (batch TTS)."""
    import requests
    import base64
    import time
    
    # DETERMINE SOURCE
    ai_chunks = app_state.get('ai_image_chunks', [])
    claim_chunks = app_state.get('claim_screenshots', [])
    
    if ai_chunks:
        chunks = ai_chunks
        source_type = 'ai'
        print(f"🔊 Generating audio for {len(chunks)} AI chunks")
    else:
        chunks = claim_chunks
        source_type = 'claim'
        print(f"🔊 Generating audio for {len(chunks)} claim chunks")
        
    if not chunks:
        return jsonify({'success': False, 'error': 'No chunks available'}), 400
    
    api_key = os.getenv('GOOGLE_CLOUD_API_KEY') or os.getenv('GEMINI_API_KEY', '')
    if not api_key:
        return jsonify({'success': False, 'error': 'API key not set (need GOOGLE_CLOUD_API_KEY or GEMINI_API_KEY)'}), 500
    
    audio_dir = TMP_DIR / 'audio'
    audio_dir.mkdir(exist_ok=True)
    
    results = []
    for i, chunk in enumerate(chunks):
        # Handle different text keys
        if source_type == 'ai':
            text = chunk.get('text', chunk.get('chunk_text', ''))
        else:
            text = chunk.get('chunk_text', chunk.get('claim', ''))
            
        # Clean text
        clean_text = re.sub(r'\[.*?\]', '', text)
        clean_text = re.sub(r'https?://\S+', '', clean_text)
        # Strip "Shot 1:", "Chunk 1:", "Script 1:", etc from start of lines
        clean_text = re.sub(r'(?i)^(Shot|Chunk|Script|Scene)\s+\d+[:.]?\s*', '', clean_text)
        # Also handle potential mid-text labels if splitter failed weirdly
        clean_text = clean_text.strip()
        
        # TTS pronunciation fixes for common abbreviations
        # "US" causes awkward pause - expand to full word
        clean_text = re.sub(r'\bUS\b(?!\s+dollars)', 'United States', clean_text)  # US but not "US dollars"
        clean_text = re.sub(r'\bUS\s+dollars\b', 'U.S. dollars', clean_text)  # Keep "U.S. dollars" natural
        clean_text = re.sub(r'\bUSA\b', 'United States', clean_text)
        clean_text = re.sub(r'\bUK\b', 'United Kingdom', clean_text)
        # Dollar amounts: "$35 trillion" sounds better as "35 trillion dollars"
        clean_text = re.sub(r'\$(\d+(?:\.\d+)?)\s*(trillion|billion|million)', r'\1 \2 dollars', clean_text)
        
        if not clean_text:
            results.append({'chunk_index': i, 'success': False, 'error': 'Empty text'})
            continue
        
        tts_url = f"https://texttospeech.googleapis.com/v1beta1/text:synthesize?key={api_key}"
        payload = {
            "audioConfig": {
                "audioEncoding": "LINEAR16",
                "pitch": 0,
                "speakingRate": 1
            },
            "input": {"text": clean_text},
            "voice": {"languageCode": "en-US", "name": "en-US-Chirp3-HD-Charon"}
        }
        
        try:
            response = requests.post(tts_url, json=payload, timeout=60)
            if response.status_code == 200:
                audio_content = response.json().get('audioContent', '')
                if audio_content:
                    audio_bytes = base64.b64decode(audio_content)
                    filename = f"chunk_{i}_{int(time.time())}.wav"
                    filepath = audio_dir / filename
                    with open(filepath, 'wb') as f:
                        f.write(audio_bytes)
                    results.append({
                        'chunk_index': i,
                        'success': True,
                        'audio_url': f'/api/audio/{filename}',
                        'path': str(filepath)
                    })
                else:
                    results.append({'chunk_index': i, 'success': False, 'error': 'No audio'})
            else:
                error_detail = response.text[:500] if response.text else 'Unknown error'
                print(f"TTS Error for chunk {i}: {response.status_code} - {error_detail}")
                results.append({'chunk_index': i, 'success': False, 'error': f'API error: {response.status_code}'})
        except Exception as e:
            results.append({'chunk_index': i, 'success': False, 'error': str(e)})
        
        # Rate limiting
        time.sleep(0.5)
    
    successful = len([r for r in results if r.get('success')])
    return jsonify({
        'success': True,
        'results': results,
        'total': len(chunks),
        'successful': successful,
        'message': f'Generated audio for {successful}/{len(chunks)} chunks'
    })


@app.route('/api/clear-audio', methods=['POST'])
def api_clear_audio():
    """Clear all audio files without affecting screenshots."""
    audio_dir = TMP_DIR / 'audio'
    
    if not audio_dir.exists():
        return jsonify({'success': True, 'message': 'No audio directory found', 'deleted': 0})
    
    deleted_count = 0
    for audio_file in audio_dir.glob('*.wav'):
        try:
            audio_file.unlink()
            deleted_count += 1
        except Exception as e:
            print(f"Failed to delete {audio_file}: {e}")
    
    for audio_file in audio_dir.glob('*.mp3'):
        try:
            audio_file.unlink()
            deleted_count += 1
        except Exception as e:
            print(f"Failed to delete {audio_file}: {e}")
    
    return jsonify({
        'success': True,
        'deleted': deleted_count,
        'message': f'Deleted {deleted_count} audio files'
    })


@app.route('/api/build-video', methods=['POST'])
def api_build_video():
    """Build final video from chunks with audio and screenshots."""
    if not check_ffmpeg():
        return jsonify({
            'success': False,
            'error': 'FFmpeg is not installed. Install with: brew install ffmpeg'
        }), 500
    # Prioritize AI image chunks over claim screenshots
    ai_chunks = app_state.get('ai_image_chunks', [])
    claim_chunks = app_state.get('claim_screenshots', [])
    
    if ai_chunks:
        chunks = ai_chunks
        source_type = 'ai'
        print(f"🎬 Building video from {len(chunks)} AI image chunks")
    elif claim_chunks:
        chunks = claim_chunks
        source_type = 'claim'
        print(f"🎬 Building video from {len(chunks)} claim screenshot chunks")
    else:
        return jsonify({'success': False, 'error': 'No chunks available'}), 400
    
    # Get stock video selections from request (if any)
    request_data = request.get_json() or {}
    chunk_stock_videos = {}
    if request_data.get('chunks'):
        for c in request_data['chunks']:
            chunk_stock_videos[c['index']] = c.get('stock_videos', {})
    
    audio_dir = TMP_DIR / 'audio'
    stock_dir = TMP_DIR / 'stock'
    
    # Build chunk data for video generation
    video_chunks = []
    for i, chunk in enumerate(chunks):
        # Find audio file for this chunk - support both formats
        audio_path = None
        for pattern in [f"chunk_{i}.wav", f"chunk_{i}.mp3", f"chunk_{i}_*.wav", f"chunk_{i}_*.mp3"]:
            audio_files = list(audio_dir.glob(pattern))
            if audio_files:
                audio_path = str(max(audio_files, key=lambda p: p.stat().st_mtime))
                break
        
        if not audio_path:
            continue  # Skip chunks without audio
        
        # Get stock video path if selected
        stock_video_path = None
        stock_videos = chunk_stock_videos.get(i, {})
        # Prefer negative (more impactful), then positive
        if stock_videos.get('negative'):
            potential_path = stock_dir / 'negative' / stock_videos['negative']
            if potential_path.exists():
                stock_video_path = str(potential_path)
        elif stock_videos.get('positive'):
            potential_path = stock_dir / 'positive' / stock_videos['positive']
            if potential_path.exists():
                stock_video_path = str(potential_path)
        
        # Check for custom uploaded video (takes priority over stock videos)
        custom_video_path = chunk.get('custom_video_path')
        if custom_video_path and os.path.exists(custom_video_path):
            # Custom uploaded video takes priority
            final_video_path = custom_video_path
        else:
            final_video_path = stock_video_path
        
        # Extract text and screenshot based on source type
        if source_type == 'ai':
            chunk_text = chunk.get('text', chunk.get('chunk_text', ''))[:50]
            # AI chunks have image_url like /api/ai-images/batch_xxx/chunk_001.png
            # Convert to local path
            image_url = chunk.get('image_url', '')
            if image_url.startswith('/api/ai-images/'):
                rel_path = image_url.replace('/api/ai-images/', '')
                screenshot_path = str(TMP_DIR / 'ai_images' / rel_path)
            else:
                screenshot_path = chunk.get('path')
        else:
            chunk_text = chunk.get('chunk_text', chunk.get('claim', ''))[:50]
            screenshot_path = chunk.get('filepath', chunk.get('local_path')) if chunk.get('success') else None
        
        video_chunks.append({
            'id': i,
            'text': chunk_text,
            'audio_path': audio_path,
            'screenshot_path': screenshot_path,
            'stock_video_path': final_video_path  # Uses custom video if available, else stock video
        })
    
    if not video_chunks:
        return jsonify({'success': False, 'error': 'No chunks with audio found'}), 400
    
    # Build video
    result = build_video_from_chunks(video_chunks)
    
    
    if result['success']:
        # Make output accessible via web
        output_path = result['output_path']
        filename = os.path.basename(output_path)
        
        return jsonify({
            'success': True,
            'message': result['message'],
            'video_url': f'/api/video/{filename}',
            'duration': result.get('duration', 0),
            'segments_count': result.get('segments_count', 0)
        })
    else:
        return jsonify({'success': False, 'error': result['message']}), 500


@app.route('/api/video/<path:filename>')
def serve_video(filename):
    """Serve generated video files."""
    output_dir = TMP_DIR / 'final_videos'
    return send_from_directory(output_dir, filename, mimetype='video/mp4')


@app.route('/api/list-videos')
def api_list_videos():
    """List all videos in the final_videos folder for subtitle testing."""
    output_dir = TMP_DIR / 'final_videos'
    output_dir.mkdir(exist_ok=True)
    
    videos = []
    for video_file in output_dir.glob('*.mp4'):
        # Get file info
        stat = video_file.stat()
        videos.append({
            'filename': video_file.name,
            'size_mb': round(stat.st_size / (1024 * 1024), 1),
            'modified': stat.st_mtime,
            'is_subtitled': '_subtitled' in video_file.stem,
            'url': f'/api/video/{video_file.name}'
        })
    
    # Sort by modified time, newest first
    videos.sort(key=lambda x: x['modified'], reverse=True)
    
    return jsonify({
        'success': True,
        'videos': videos,
        'count': len(videos)
    })


@app.route('/api/add-subtitles', methods=['POST'])
def api_add_subtitles():
    """
    Generate and burn subtitles into a video.
    Uses Gemini for transcription, FFmpeg for burning.
    Expected JSON: { video_filename } OR uses latest video if not specified.
    """
    from execution.generate_subtitles import generate_subtitled_video
    
    data = request.json or {}
    video_filename = data.get('video_filename')
    
    # Find the video file
    output_dir = TMP_DIR / 'final_videos'
    
    if video_filename:
        video_path = output_dir / video_filename
    else:
        # Use the most recent video
        videos = list(output_dir.glob('*.mp4'))
        # Exclude already subtitled videos
        videos = [v for v in videos if '_subtitled' not in v.stem]
        if not videos:
            return jsonify({'success': False, 'error': 'No videos found'}), 404
        video_path = max(videos, key=lambda p: p.stat().st_mtime)
    
    if not video_path.exists():
        return jsonify({'success': False, 'error': f'Video not found: {video_filename}'}), 404
    
    print(f"📝 Generating subtitles for: {video_path.name}")
    
    result = generate_subtitled_video(
        video_path=str(video_path),
        output_dir=str(output_dir)
    )
    
    if result['success']:
        subtitled_filename = Path(result['subtitled_video']).name
        # Store SRT path for download
        if result.get('srt_path'):
            app_state['last_srt_path'] = result['srt_path']
        return jsonify({
            'success': True,
            'message': 'Subtitles generated and burned successfully',
            'original_video': f'/api/video/{video_path.name}',
            'subtitled_video': f'/api/video/{subtitled_filename}',
            'srt_file': f'/api/download-srt',  # URL for download
            'srt_path': result.get('srt_path'),
            'ass_path': result.get('ass_path')
        })
    else:
        return jsonify({'success': False, 'error': result.get('error', 'Unknown error')}), 500


@app.route('/api/download-srt', methods=['GET'])
def api_download_srt():
    """Download the most recently generated SRT file."""
    srt_path = app_state.get('last_srt_path')
    
    if not srt_path or not Path(srt_path).exists():
        # Try to find any SRT in temp directory
        srt_files = list((TMP_DIR / 'final_videos').glob('*.srt'))
        if srt_files:
            srt_path = str(max(srt_files, key=lambda p: p.stat().st_mtime))
        else:
            return jsonify({'error': 'No SRT file available'}), 404
    
    return send_file(
        srt_path,
        mimetype='text/plain',
        as_attachment=True,
        download_name='subtitles.srt'
    )


@app.route('/api/upload-chunk-screenshot', methods=['POST'])
def api_upload_chunk_screenshot():
    """Upload a new screenshot for a specific chunk."""
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': 'No file provided'}), 400
    
    file = request.files['file']
    chunk_index = request.form.get('chunk_index', type=int)
    
    if chunk_index is None:
        return jsonify({'success': False, 'error': 'No chunk_index provided'}), 400
    
    if not file.filename:
        return jsonify({'success': False, 'error': 'No file selected'}), 400
    
    # Save the uploaded file
    import time
    filename = f"chunk_{chunk_index}_upload_{int(time.time())}.png"
    filepath = SCREENSHOTS_DIR / filename
    file.save(filepath)
    
    # Update the chunk in app_state
    chunks = app_state.get('claim_screenshots', [])
    if chunk_index < len(chunks):
        chunks[chunk_index]['filepath'] = str(filepath)
        chunks[chunk_index]['filename'] = filename
        chunks[chunk_index]['success'] = True
        
        # Save updated manifest
        manifest_path = SCREENSHOTS_DIR / 'claim_screenshots_manifest.json'
        with open(manifest_path, 'w') as f:
            json.dump(chunks, f, indent=2)
    
    return jsonify({
        'success': True,
        'chunk_index': chunk_index,
        'filepath': str(filepath),
        'screenshot_url': f'/api/screenshots/{filename}'
    })


@app.route('/api/upload-chunk-video', methods=['POST'])
def api_upload_chunk_video():
    """Upload a custom video for a specific chunk."""
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': 'No file provided'}), 400
    
    file = request.files['file']
    chunk_index = request.form.get('chunk_index', type=int)
    
    if chunk_index is None:
        return jsonify({'success': False, 'error': 'No chunk_index provided'}), 400
    
    if not file.filename:
        return jsonify({'success': False, 'error': 'No file selected'}), 400
    
    # Create chunk videos directory
    chunk_videos_dir = TMP_DIR / 'chunk_videos'
    chunk_videos_dir.mkdir(exist_ok=True)
    
    # Save the uploaded video
    import time
    ext = os.path.splitext(file.filename)[1] or '.mp4'
    filename = f"chunk_{chunk_index}_video_{int(time.time())}{ext}"
    filepath = chunk_videos_dir / filename
    file.save(filepath)
    
    # Update the chunk in app_state
    chunks = app_state.get('claim_screenshots', [])
    if chunk_index < len(chunks):
        chunks[chunk_index]['custom_video_path'] = str(filepath)
        
        # Save updated manifest
        manifest_path = SCREENSHOTS_DIR / 'claim_screenshots_manifest.json'
        with open(manifest_path, 'w') as f:
            json.dump(chunks, f, indent=2)
    
    return jsonify({
        'success': True,
        'chunk_index': chunk_index,
        'video_path': str(filepath),
        'video_url': f'/api/chunk-video/{filename}'
    })


@app.route('/api/chunk-video/<filename>')
def serve_chunk_video(filename):
    """Serve uploaded chunk videos."""
    chunk_videos_dir = TMP_DIR / 'chunk_videos'
    return send_from_directory(chunk_videos_dir, filename)


@app.route('/api/copy-chunk-screenshot', methods=['POST'])
def api_copy_chunk_screenshot():
    """Copy screenshot from one chunk to another (for 'Use Previous' feature)."""
    data = request.json
    source_index = data.get('source_index')
    target_index = data.get('target_index')
    
    if source_index is None or target_index is None:
        return jsonify({'success': False, 'error': 'source_index and target_index required'}), 400
    
    chunks = app_state.get('claim_screenshots', [])
    
    if source_index >= len(chunks) or not chunks[source_index].get('success'):
        return jsonify({'success': False, 'error': 'Source chunk has no screenshot'}), 400
    
    # Copy the file
    import shutil
    import time
    source_path = Path(chunks[source_index].get('filepath', ''))
    
    if not source_path.exists():
        return jsonify({'success': False, 'error': 'Source file not found'}), 400
    
    new_filename = f"chunk_{target_index}_copied_{int(time.time())}.png"
    new_path = SCREENSHOTS_DIR / new_filename
    shutil.copy2(source_path, new_path)
    
    # Update target chunk
    if target_index < len(chunks):
        chunks[target_index]['filepath'] = str(new_path)
        chunks[target_index]['filename'] = new_filename
        chunks[target_index]['success'] = True
        chunks[target_index]['copied_from'] = source_index
        
        # Save manifest
        manifest_path = SCREENSHOTS_DIR / 'claim_screenshots_manifest.json'
        with open(manifest_path, 'w') as f:
            json.dump(chunks, f, indent=2)
    
    return jsonify({
        'success': True,
        'screenshot_url': f'/api/screenshots/{new_filename}'
    })


@app.route('/api/regenerate-chunk-screenshot', methods=['POST'])
def api_regenerate_chunk_screenshot():
    """
    Regenerate screenshot for a chunk using the next available Serper result.
    Allows cycling through results (2nd, 3rd, etc.) when 1st result fails.
    """
    from execution.claim_screenshots import search_claim, extract_claim
    
    data = request.json
    chunk_index = data.get('chunk_index')
    result_index = data.get('result_index', 1)  # 0=1st, 1=2nd, 2=3rd
    allow_duplicates = data.get('allow_duplicates', True)  # Override unique URL rule
    
    if chunk_index is None:
        return jsonify({'success': False, 'error': 'chunk_index required'}), 400
    
    chunks = app_state.get('claim_screenshots', [])
    if chunk_index >= len(chunks):
        return jsonify({'success': False, 'error': 'Invalid chunk index'}), 400
    
    chunk = chunks[chunk_index]
    chunk_text = chunk.get('chunk_text', chunk.get('claim', ''))
    
    if not chunk_text:
        return jsonify({'success': False, 'error': 'No text for this chunk'}), 400
    
    # Blacklisted domains (same as JS capture script)
    BLACKLISTED_DOMAINS = [
        'twitter.com', 'x.com', 'facebook.com', 'instagram.com', 'linkedin.com',
        'wsj.com', 'nytimes.com', 'nyt.com', 'ft.com', 'bloomberg.com',
        'washingtonpost.com', 'economist.com', 'forbes.com', 'reuters.com',
        'time.com', 'theglobeandmail.com', 'dw.com', 'cbsnews.com',
        'news.sky.com', 'sky.com', 'azerbaycan24.com', 'vocal.media'
    ]
    
    def is_blacklisted(url):
        for domain in BLACKLISTED_DOMAINS:
            if domain in url.lower():
                return True
        return False
    
    # Re-extract claim and search
    claim = extract_claim(chunk_text)
    all_results = search_claim(claim, include_twitter=False)
    
    # Filter out blacklisted URLs
    results = [r for r in all_results if not is_blacklisted(r.get('url', ''))]
    
    print(f"DEBUG: Serper returned {len(all_results)} results, {len(results)} after blacklist filter")
    
    if not results:
        return jsonify({
            'success': False, 
            'error': 'All results are from blacklisted domains. Try a different chunk.',
            'available_results': 0
        }), 400
    
    # Clamp result_index to available results
    if result_index >= len(results):
        result_index = len(results) - 1
    
    target_url = results[result_index]['url']
    print(f"DEBUG: Using result {result_index + 1}/{len(results)}: {target_url}")
    
    # Capture screenshot from this specific URL
    import subprocess
    
    # Create single-chunk data for the screenshot script
    single_chunk_data = {
        'video_name': 'regen',
        'chunks': [{
            'chunk_index': chunk_index,
            'chunk_text': chunk_text,
            'claim': claim,
            'urls': [target_url],
            'titles': [results[result_index].get('title', '')]
        }]
    }
    
    data_file = TMP_DIR / 'regen_screenshot_data.json'
    with open(data_file, 'w') as f:
        json.dump(single_chunk_data, f)
    
    try:
        print(f"DEBUG: Running screenshot capture for chunk {chunk_index}, URL: {target_url}")
        result = subprocess.run(
            ['node', 'execution/capture_claim_screenshots.js', '--data', str(data_file)],
            capture_output=True,
            text=True,
            cwd=str(BASE_DIR),
            timeout=120
        )
        
        print(f"DEBUG: Node stdout length: {len(result.stdout)}")
        print(f"DEBUG: Node stderr: {result.stderr[:500] if result.stderr else 'None'}")
        
        # Parse result
        output = result.stdout
        json_match = re.search(r'__JSON_START__\s*(.*?)\s*__JSON_END__', output, re.DOTALL)
        
        if json_match:
            screenshot_results = json.loads(json_match.group(1))
            print(f"DEBUG: Screenshot results: {screenshot_results}")
            
            if screenshot_results and screenshot_results[0].get('success'):
                ss = screenshot_results[0]
                
                # Update chunk in app_state
                chunks[chunk_index]['filepath'] = ss['filepath']
                chunks[chunk_index]['filename'] = ss['filename']
                chunks[chunk_index]['success'] = True
                chunks[chunk_index]['url'] = target_url
                chunks[chunk_index]['result_index'] = result_index
                
                # Save manifest
                manifest_path = SCREENSHOTS_DIR / 'claim_screenshots_manifest.json'
                with open(manifest_path, 'w') as f:
                    json.dump(chunks, f, indent=2)
                
                return jsonify({
                    'success': True,
                    'screenshot_url': f"/api/screenshots/{ss['filename']}",
                    'result_index': result_index,
                    'source_url': target_url,
                    'available_results': len(results)
                })
            else:
                error_msg = screenshot_results[0].get('error', 'Screenshot capture failed') if screenshot_results else 'No results'
                print(f"DEBUG: Screenshot failed: {error_msg}")
                return jsonify({
                    'success': False, 
                    'error': error_msg,
                    'available_results': len(results)
                })
        else:
            print(f"DEBUG: No JSON found in output. Stdout preview: {output[:500]}")
            return jsonify({
                'success': False, 
                'error': 'No valid output from screenshot script',
                'available_results': len(results)
            })
            
    except subprocess.TimeoutExpired:
        return jsonify({'success': False, 'error': 'Screenshot capture timed out (120s)'}), 500
    except Exception as e:
        print(f"DEBUG: Exception during regenerate: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': f'Screenshot capture failed: {str(e)}'}), 500


@app.route('/api/stock-videos')
def api_stock_videos():
    """List available stock videos in positive and negative folders."""
    stock_dir = TMP_DIR / 'stock'
    positive_dir = stock_dir / 'positive'
    negative_dir = stock_dir / 'negative'
    
    video_extensions = ['.mp4', '.mov', '.avi', '.mkv', '.webm']
    
    positive_videos = []
    negative_videos = []
    
    if positive_dir.exists():
        positive_videos = [f.name for f in positive_dir.iterdir() 
                          if f.is_file() and f.suffix.lower() in video_extensions]
        positive_videos.sort()
    
    if negative_dir.exists():
        negative_videos = [f.name for f in negative_dir.iterdir() 
                          if f.is_file() and f.suffix.lower() in video_extensions]
        negative_videos.sort()
    
    return jsonify({
        'success': True,
        'positive': positive_videos,
        'negative': negative_videos
    })


@app.route('/api/stock-video/<video_type>/<filename>')
def serve_stock_video(video_type, filename):
    """Serve a stock video file for preview."""
    if video_type not in ['positive', 'negative']:
        return jsonify({'error': 'Invalid video type'}), 400
    
    video_dir = TMP_DIR / 'stock' / video_type
    if not video_dir.exists():
        return jsonify({'error': 'Stock video directory not found'}), 404
    
    return send_from_directory(video_dir, filename)


@app.route('/api/custom-thumbnails')
def api_custom_thumbnails():
    """List custom thumbnails from .tmp/thumbnails/ folder."""
    thumbnails_dir = TMP_DIR / 'thumbnails'
    thumbnails_dir.mkdir(exist_ok=True)
    
    image_extensions = ['.jpg', '.jpeg', '.png', '.webp', '.gif']
    
    thumbnails = []
    if thumbnails_dir.exists():
        for f in thumbnails_dir.iterdir():
            if f.is_file() and f.suffix.lower() in image_extensions:
                thumbnails.append({
                    'name': f.name,
                    'path': f'/api/serve-thumbnail/{f.name}'
                })
        thumbnails.sort(key=lambda x: x['name'])
    
    return jsonify({
        'success': True,
        'thumbnails': thumbnails,
        'folder': str(thumbnails_dir)
    })


@app.route('/api/serve-thumbnail/<filename>')
def api_serve_thumbnail(filename):
    """Serve a thumbnail image from .tmp/thumbnails/."""
    thumbnails_dir = TMP_DIR / 'thumbnails'
    return send_from_directory(thumbnails_dir, filename)


@app.route('/api/final-videos')
def api_final_videos():
    """List final videos from .tmp/final_videos/ folder."""
    videos_dir = TMP_DIR / 'final_videos'
    videos_dir.mkdir(exist_ok=True)
    
    video_extensions = ['.mp4', '.mov', '.avi', '.mkv', '.webm']
    
    videos = []
    if videos_dir.exists():
        for f in videos_dir.iterdir():
            if f.is_file() and f.suffix.lower() in video_extensions:
                # Get file size
                size_mb = f.stat().st_size / (1024 * 1024)
                videos.append({
                    'name': f.name,
                    'path': str(f),
                    'size_mb': round(size_mb, 1)
                })
        videos.sort(key=lambda x: x['name'], reverse=True)  # Newest first by name
    
    return jsonify({
        'success': True,
        'videos': videos,
        'folder': str(videos_dir)
    })


# ============== THUMBNAIL & TITLE GENERATOR ==============

@app.route('/api/get-saved-videos', methods=['GET'])
def api_get_saved_videos():
    """Get all saved videos with their thumbnails and current script context."""
    # Use current_project from persistent_data (same as Saved tab)
    current_project = persistent_data.get('current_project')
    
    # Get saved videos for current project (or all if no project)
    all_saved = persistent_data.get('saved_videos', {})
    unique_videos = {}  # Use dict to dedupe by ID
    
    # If we have a current project, prioritize those videos
    if current_project and current_project in all_saved:
        for video in all_saved[current_project]:
            video_id = video.get('video_id', '')
            if video_id:
                unique_videos[video_id] = {
                    'id': video.get('id', video_id),
                    'video_id': video_id,
                    'title': video.get('title', 'Untitled'),
                    'url': video.get('url', f'https://youtube.com/watch?v={video_id}'),
                    'thumbnail_url': f"https://img.youtube.com/vi/{video_id}/mqdefault.jpg",
                    'project_id': current_project
                }
    else:
        # Fallback: get videos from all projects
        for pid, videos in all_saved.items():
            for video in videos:
                video_id = video.get('video_id', '')
                if video_id:
                    unique_videos[video_id] = {
                        'id': video.get('id', video_id),
                        'video_id': video_id,
                        'title': video.get('title', 'Untitled'),
                        'url': video.get('url', f'https://youtube.com/watch?v={video_id}'),
                        'thumbnail_url': f"https://img.youtube.com/vi/{video_id}/mqdefault.jpg",
                        'project_id': pid
                    }
    
    # Get current script context
    script_context = {}
    script_data = app_state.get('script')
    if script_data and isinstance(script_data, dict):
        # Script is a dict with 'title', 'raw_text', 'analysis' fields
        raw_text = script_data.get('raw_text', '')
        title = script_data.get('title', '')  # e.g., "Script: Venezuela Oil War"
        
        # Extract topic from title (removes "Script: " prefix)
        topic = title.replace('Script:', '').strip() if title else ''
        
        # If no topic from title, try to extract from first line of raw_text
        if not topic and raw_text:
            first_line = raw_text.split('\n')[0].strip()
            # Remove markdown headers and common prefixes
            topic = first_line.lstrip('#').strip()
            if topic.startswith('[HOOK]') or topic.startswith('HOOK:'):
                # Get the actual content after the section header
                topic = topic.replace('[HOOK]', '').replace('HOOK:', '').strip()[:100]
        
        script_context = {
            'topic': topic,
            'summary': raw_text[:1500] if raw_text else ''  # First ~1500 chars as outline
        }

    return jsonify({
        'success': True, 
        'videos': list(unique_videos.values()),
        'context': script_context
    })


@app.route('/api/analyze-thumbnail', methods=['POST'])
def api_analyze_thumbnail():
    """Dissect a thumbnail into 5 structured components for editing."""
    data = request.json
    video_id = data.get('video_id')
    
    if not video_id:
        return jsonify({'success': False, 'error': 'No video_id provided'}), 400
    
    api_key = os.getenv('GEMINI_API_KEY', '')
    if not api_key:
        return jsonify({'success': False, 'error': 'GEMINI_API_KEY not set'}), 500
    
    # Download thumbnail first
    thumbnail_path = download_thumbnail(video_id)
    if not thumbnail_path:
        return jsonify({'success': False, 'error': 'Failed to download thumbnail'}), 500
    
    # Dissect with Gemini Vision
    result = dissect_thumbnail(thumbnail_path, api_key)
    
    if result.get('success'):
        return jsonify({
            'success': True,
            'dissection': result.get('dissection'),
            'thumbnail_path': thumbnail_path,
            'video_id': video_id
        })
    else:
        return jsonify({'success': False, 'error': result.get('error'), 'raw': result.get('raw', '')}), 500


@app.route('/api/generate-thumbnail-prompt', methods=['POST'])
def api_generate_thumbnail_prompt():
    """Generate a prompt for AI thumbnail creation."""
    data = request.json
    analysis = data.get('analysis', {})
    topic = data.get('topic', '')
    style_notes = data.get('style_notes', '')
    
    if not topic:
        return jsonify({'success': False, 'error': 'Topic is required'}), 400
    
    prompt = generate_thumbnail_prompt(analysis, topic, style_notes)
    
    return jsonify({
        'success': True,
        'prompt': prompt
    })


@app.route('/api/generate-thumbnail-image', methods=['POST'])
def api_generate_thumbnail_image():
    """Generate a thumbnail using structured component inputs."""
    import base64
    import time
    
    data = request.json
    video_id = data.get('video_id')  # Reference video
    
    # Structured component inputs
    original_dissection = data.get('original', {})  # The original dissection from analyze
    overrides = data.get('overrides', {})  # What the user wants to change
    
    if not video_id:
        return jsonify({'success': False, 'error': 'video_id is required'}), 400
    
    api_key = os.getenv('GEMINI_API_KEY', '')
    if not api_key:
        return jsonify({'success': False, 'error': 'GEMINI_API_KEY not set'}), 500
    
    # Download reference thumbnail
    thumbnail_url = f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg"
    try:
        thumb_response = requests.get(thumbnail_url, timeout=10)
        if thumb_response.status_code != 200:
            thumbnail_url = f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg"
            thumb_response = requests.get(thumbnail_url, timeout=10)
        
        if thumb_response.status_code != 200:
            return jsonify({'success': False, 'error': 'Failed to download reference thumbnail'}), 500
        
        ref_image_base64 = base64.b64encode(thumb_response.content).decode('utf-8')
    except Exception as e:
        return jsonify({'success': False, 'error': f'Failed to download thumbnail: {e}'}), 500
    
    # Build structured prompt from components
    prompt_parts = ["RECREATE this YouTube thumbnail with the following specifications:"]
    prompt_parts.append("")
    
    # 1. PERSON - Use override or keep original
    person_desc = overrides.get('person') or (original_dissection.get('person', {}).get('description', ''))
    if person_desc:
        prompt_parts.append(f"PERSON: {person_desc}")
        prompt_parts.append("- Keep this person EXACTLY the same (face, appearance)")
    prompt_parts.append("")
    
    # 2. EXPRESSION - Use override or keep original
    expr_override = overrides.get('expression')
    if expr_override:
        prompt_parts.append(f"EXPRESSION: Change to: {expr_override}")
    else:
        orig_expr = original_dissection.get('expression', {})
        if orig_expr:
            prompt_parts.append(f"EXPRESSION: Keep the same - {orig_expr.get('description', '')}")
    prompt_parts.append("")
    
    # 3. TEXT - This is the key override
    text_override = overrides.get('text')
    if text_override:
        prompt_parts.append("TEXT: REPLACE all text with:")
        prompt_parts.append(f'"{text_override}"')
        prompt_parts.append("- ERASE all original text completely")
        prompt_parts.append("- Write the new text in similar style/position")
    else:
        orig_text = original_dissection.get('text', [])
        if orig_text:
            text_contents = [t.get('content', '') for t in orig_text if isinstance(t, dict)]
            prompt_parts.append(f"TEXT: Keep original text: {', '.join(text_contents)}")
    prompt_parts.append("")
    
    # 4. COLORS - Use override or keep original
    color_override = overrides.get('colors')
    if color_override:
        prompt_parts.append(f"COLORS: Change color scheme to: {color_override}")
    else:
        orig_colors = original_dissection.get('colors', {})
        if orig_colors:
            prompt_parts.append(f"COLORS: Keep original - Primary: {orig_colors.get('primary', 'N/A')}, Secondary: {orig_colors.get('secondary', 'N/A')}")
    prompt_parts.append("")
    
    # 5. GRAPHICS - Use override or keep original
    graphics_override = overrides.get('graphics')
    if graphics_override:
        prompt_parts.append(f"GRAPHICS/BACKGROUND: {graphics_override}")
    else:
        orig_graphics = original_dissection.get('graphics', {})
        if orig_graphics:
            prompt_parts.append(f"GRAPHICS: Keep original background - {orig_graphics.get('description', '')}")
    prompt_parts.append("")
    
    prompt_parts.append("OUTPUT: Professional YouTube thumbnail, 1280x720 pixels, high quality")
    
    prompt = "\n".join(prompt_parts)
    
    # Call Gemini with image input
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-exp-image-generation:generateContent?key={api_key}"
    
    payload = {
        "contents": [{
            "parts": [
                {
                    "inlineData": {
                        "mimeType": "image/jpeg",
                        "data": ref_image_base64
                    }
                },
                {"text": prompt}
            ]
        }],
        "generationConfig": {
            "responseModalities": ["TEXT", "IMAGE"]
        }
    }
    
    try:
        response = requests.post(url, json=payload, timeout=120)
        if response.status_code == 200:
            result = response.json()
            
            for candidate in result.get('candidates', []):
                for part in candidate.get('content', {}).get('parts', []):
                    if 'inlineData' in part:
                        image_data = part['inlineData']['data']
                        
                        filename = f"thumbnail_{int(time.time())}.png"
                        filepath = TMP_DIR / 'thumbnails' / filename
                        filepath.parent.mkdir(parents=True, exist_ok=True)
                        
                        with open(filepath, 'wb') as f:
                            f.write(base64.b64decode(image_data))
                        
                        return jsonify({
                            'success': True,
                            'image_url': f'/api/thumbnails/{filename}',
                            'filepath': str(filepath),
                            'prompt_used': prompt
                        })
            
            return jsonify({'success': False, 'error': 'No image in response'})
        else:
            return jsonify({'success': False, 'error': f'API error: {response.status_code} - {response.text[:300]}'}), 500
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/thumbnails/<path:filename>')
def serve_thumbnail(filename):
    """Serve generated thumbnail files."""
    return send_from_directory(TMP_DIR / 'thumbnails', filename)

@app.route('/api/video-info/<video_id>')
def api_video_info(video_id):
    """Fetch detailed video info (tags, description, stats) from YouTube API."""
    result = get_video_details(video_id)
    
    if result.get('success'):
        # Format duration for display
        if result.get('duration'):
            result['duration_formatted'] = format_duration(result['duration'])
        return jsonify(result)
    else:
        return jsonify(result), 500


@app.route('/api/finalize', methods=['POST'])
def api_finalize():
    """Save finalized items (thumbnail, title, description, tags) for posting."""
    data = request.json
    item_type = data.get('type')  # 'thumbnail', 'title', 'description', 'tags'
    value = data.get('value')
    
    if not item_type or not value:
        return jsonify({'success': False, 'error': 'type and value required'}), 400
    
    # Store in app_state
    if 'finalized' not in app_state:
        app_state['finalized'] = {}
    
    app_state['finalized'][item_type] = value
    
    return jsonify({
        'success': True,
        'message': f'{item_type} finalized',
        'finalized': app_state['finalized']
    })


@app.route('/api/finalized')
def api_get_finalized():
    """Get all finalized items."""
    return jsonify({
        'success': True,
        'finalized': app_state.get('finalized', {})
    })


@app.route('/api/rewrite-description', methods=['POST'])
def api_rewrite_description():
    """Rewrite a video description using AI."""
    data = request.json
    description = data.get('description', '')
    
    if not description:
        return jsonify({'success': False, 'error': 'No description provided'}), 400
    
    api_key = os.getenv('GEMINI_API_KEY', '')
    if not api_key:
        return jsonify({'success': False, 'error': 'GEMINI_API_KEY not set'}), 500
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"
    
    prompt = f"""Rewrite this YouTube video description to be more engaging and optimized for search.
Keep the same general information but make it more compelling.
Add relevant hashtags at the end.
Keep it under 5000 characters.

Original description:
{description}

Write only the new description, no explanations."""

    try:
        response = requests.post(url, json={
            "contents": [{"parts": [{"text": prompt}]}]
        }, timeout=60)
        
        if response.status_code == 200:
            result = response.json()
            rewritten = result['candidates'][0]['content']['parts'][0]['text']
            return jsonify({'success': True, 'rewritten': rewritten})
        else:
            return jsonify({'success': False, 'error': 'API error'}), 500
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/check-video-file')
def api_check_video_file():
    """Check if a video file exists in the uploads folder."""
    uploads_dir = TMP_DIR / 'uploads'
    uploads_dir.mkdir(parents=True, exist_ok=True)
    
    video_extensions = ['.mp4', '.mov', '.avi', '.mkv', '.webm']
    
    for file in uploads_dir.iterdir():
        if file.is_file() and file.suffix.lower() in video_extensions:
            size_mb = round(file.stat().st_size / (1024 * 1024), 2)
            return jsonify({
                'found': True,
                'filename': file.name,
                'path': str(file),
                'size_mb': size_mb
            })
    
    return jsonify({'found': False})


# ============== YOUTUBE UPLOAD ==============

@app.route('/api/youtube/auth-status')
def api_youtube_auth_status():
    """Check YouTube authentication status."""
    deps = check_dependencies()
    return jsonify({
        'authenticated': is_authenticated(),
        'dependencies': deps
    })


@app.route('/api/youtube/auth')
def api_youtube_auth():
    """Start YouTube OAuth flow."""
    result = get_auth_url()
    if result.get('success'):
        # Store state in session for validation
        session['oauth_state'] = result.get('state')
        return redirect(result['auth_url'])
    else:
        return jsonify(result), 500


@app.route('/oauth2callback')
def oauth2callback():
    """Handle OAuth callback from Google."""
    # Get the full URL for token exchange
    authorization_response = request.url
    
    result = handle_oauth_callback(authorization_response)
    
    if result.get('success'):
        # Redirect to Post tab with success message
        return redirect('/?tab=11&auth=success')
    else:
        return f"Authorization failed: {result.get('error')}", 400


@app.route('/api/youtube/upload', methods=['POST'])
def api_youtube_upload():
    """Upload video to YouTube."""
    # Check authentication
    if not is_authenticated():
        return jsonify({'success': False, 'error': 'Not authenticated. Click "Connect YouTube" first.'}), 401
    
    # Get request data
    data = request.json or {}
    
    # Get finalized data
    finalized = app_state.get('finalized', {})
    title = finalized.get('title')
    description = finalized.get('description', '')
    tags = finalized.get('tags', [])
    thumbnail_data = finalized.get('thumbnail')
    
    # 1. Handle Video Path
    # First check if specific video was selected
    video_path = data.get('video_path')
    
    # If not, look in final_videos folder (new location)
    if not video_path:
        videos_dir = TMP_DIR / 'final_videos'
        if videos_dir.exists():
            # Get most recent video
            videos = list(videos_dir.glob('*.mp4'))
            if videos:
                videos.sort(key=os.path.getmtime, reverse=True)
                video_path = str(videos[0])
    
    # Fallback to old uploads folder
    if not video_path:
        uploads_dir = TMP_DIR / 'uploads'
        if uploads_dir.exists():
            for file in uploads_dir.iterdir():
                if file.suffix.lower() in ['.mp4', '.mov', '.avi', '.mkv', '.webm']:
                    video_path = str(file)
                    break
            
    if not video_path or not os.path.exists(video_path):
        return jsonify({'success': False, 'error': 'No video file found. Please generate or select a video.'}), 400

    # Default title if missing (Required by YouTube API)
    if not title:
        from datetime import datetime
        filename = Path(video_path).stem
        title = f"{filename} - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    
    # Get privacy status from request
    privacy = data.get('privacy', 'private')
    
    # 2. Handle Thumbnail
    thumbnail_path = None
    
    # Case A: Custom thumbnail object from frontend
    if isinstance(thumbnail_data, dict) and thumbnail_data.get('url'):
        url = thumbnail_data.get('url')
        if '/api/serve-thumbnail/' in url:
            filename = url.split('/')[-1]
            thumbnail_path = str(TMP_DIR / 'thumbnails' / filename)
        else:
            # Handle other URL types if needed
            thumbnail_path = url
            
    # Case B: String URL (legacy)
    elif isinstance(thumbnail_data, str):
        if thumbnail_data.startswith('/api/thumbnails/'):
            filename = thumbnail_data.split('/')[-1]
            thumbnail_path = str(TMP_DIR / 'thumbnails' / filename)
        elif thumbnail_data.startswith('/api/serve-thumbnail/'):
            filename = thumbnail_data.split('/')[-1]
            thumbnail_path = str(TMP_DIR / 'thumbnails' / filename)

    print(f"DEBUG: Video Path: {video_path}")
    print(f"DEBUG: Thumbnail Path: {thumbnail_path}")

    # Upload
    result = upload_video(
        video_path=video_path,
        title=title,
        description=description,
        tags=tags,
        privacy_status=privacy,
        thumbnail_path=thumbnail_path
    )
    
    if result.get('success'):
        return jsonify(result)
    else:
        return jsonify(result), 500


@app.route('/api/generate-titles', methods=['POST'])
def api_generate_titles():
    """Generate CTR-optimized title options."""
    data = request.json
    topic = data.get('topic', '')
    outline = data.get('outline', '')
    inspiration_title = data.get('inspiration_title', '')
    channel_type = data.get('channel_type', 'General')
    
    # AUTO-REFERENCE LOGIC: If no inspiration title provided, use currently selected video title
    if not inspiration_title and app_state.get('selected_videos'):
        video = app_state['selected_videos'][0]
        inspiration_title = video.get('title', '')
        print(f"Using Auto-Reference Title: {inspiration_title}")

    if not topic:
        return jsonify({'success': False, 'error': 'Topic is required'}), 400
    
    api_key = os.getenv('GEMINI_API_KEY', '')
    if not api_key:
        return jsonify({'success': False, 'error': 'GEMINI_API_KEY not set'}), 500
    
    result = generate_title_options(
        topic=topic,
        outline=outline,
        inspiration_title=inspiration_title,
        channel_type=channel_type,
        api_key=api_key
    )
    
    return jsonify(result)


@app.route('/api/keyword-research', methods=['POST'])
def api_keyword_research():
    """Research keyword difficulty and find opportunities."""
    data = request.json
    seed_keyword = data.get('keyword', '').strip()
    include_suggestions = data.get('include_suggestions', True)
    region = data.get('region', 'US')  # Default to US market
    
    if not seed_keyword:
        return jsonify({'success': False, 'error': 'Keyword is required'}), 400
    
    youtube_api_key = os.getenv('YOUTUBE_API_KEY', '')
    if not youtube_api_key:
        return jsonify({'success': False, 'error': 'YOUTUBE_API_KEY not set in .env'}), 500
    
    try:
        results = research_keywords(seed_keyword, include_suggestions=include_suggestions, region=region)
        return jsonify({
            'success': True,
            **results
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/reset', methods=['POST'])
def api_reset():
    """Reset application state."""
    global app_state
    app_state = {
        'videos': [],
        'selected_videos': [],
        'transcript': None,
        'articles': [],
        'script': None,
        'screenshots': []
    }
    return jsonify({'success': True, 'message': 'State reset'})

# ============== PROJECT MANAGEMENT ==============

@app.route('/api/projects', methods=['GET'])
def get_projects():
    """Get all projects."""
    return jsonify({
        'success': True,
        'projects': persistent_data['projects'],
        'current_project': persistent_data['current_project']
    })

@app.route('/api/projects', methods=['POST'])
def create_project():
    """Create a new project."""
    global persistent_data
    data = request.json
    niche = data.get('niche', '').strip()
    
    if not niche:
        return jsonify({'success': False, 'message': 'Niche is required'}), 400
    
    import uuid
    project_id = str(uuid.uuid4())[:8]
    
    project = {
        'id': project_id,
        'niche': niche,
        'created_at': str(Path(__file__).stat().st_mtime)  # Simple timestamp
    }
    
    persistent_data['projects'].append(project)
    persistent_data['current_project'] = project_id
    persistent_data['saved_videos'][project_id] = []
    save_persistent_data(persistent_data)
    
    return jsonify({'success': True, 'project': project})

@app.route('/api/projects/<project_id>/select', methods=['POST'])
def select_project(project_id):
    """Select a project as current."""
    global persistent_data
    
    # Check project exists
    project = next((p for p in persistent_data['projects'] if p['id'] == project_id), None)
    if not project:
        return jsonify({'success': False, 'message': 'Project not found'}), 404
    
    persistent_data['current_project'] = project_id
    save_persistent_data(persistent_data)
    
    return jsonify({'success': True, 'project': project})

# ============== SAVED VIDEOS ==============

@app.route('/api/saved-videos', methods=['GET'])
def get_saved_videos():
    """Get saved videos for current project, grouped by search query."""
    project_id = persistent_data.get('current_project')
    if not project_id:
        return jsonify({'success': False, 'message': 'No project selected'}), 400
    
    saved = persistent_data['saved_videos'].get(project_id, {})
    
    # Handle backward compatibility: if it's a list (old format), migrate to grouped format
    if isinstance(saved, list):
        # Migrate old flat list to "Uncategorized" group
        if saved:
            persistent_data['saved_videos'][project_id] = {"Uncategorized": saved}
            save_persistent_data(persistent_data)
            saved = persistent_data['saved_videos'][project_id]
        else:
            saved = {}
    
    return jsonify({'success': True, 'groups': saved})

@app.route('/api/saved-videos', methods=['POST'])
def save_video():
    """Save a video to current project, grouped by search query."""
    global persistent_data
    
    project_id = persistent_data.get('current_project')
    if not project_id:
        return jsonify({'success': False, 'message': 'No project selected. Create a project first.'}), 400
    
    data = request.json
    video = data.get('video')
    search_query = data.get('search_query', 'Uncategorized').strip() or 'Uncategorized'
    
    if not video:
        return jsonify({'success': False, 'message': 'Video data required'}), 400
    
    # Initialize project if needed
    if project_id not in persistent_data['saved_videos']:
        persistent_data['saved_videos'][project_id] = {}
    
    # Handle backward compatibility: migrate old list format
    saved = persistent_data['saved_videos'][project_id]
    if isinstance(saved, list):
        persistent_data['saved_videos'][project_id] = {"Uncategorized": saved} if saved else {}
        saved = persistent_data['saved_videos'][project_id]
    
    # Initialize query group if needed
    if search_query not in saved:
        saved[search_query] = []
    
    # Check if video already exists in ANY group
    for group_name, group_videos in saved.items():
        if any(v['video_id'] == video['video_id'] for v in group_videos):
            return jsonify({'success': False, 'message': f'Video already saved in "{group_name}"'}), 400
    
    # Add video to the query group
    saved[search_query].append(video)
    save_persistent_data(persistent_data)
    
    return jsonify({'success': True, 'message': f'Video saved to "{search_query}"', 'group': search_query})

@app.route('/api/saved-videos/<video_id>', methods=['DELETE'])
def remove_saved_video(video_id):
    """Remove a video from saved list, searching across all groups."""
    global persistent_data
    
    project_id = persistent_data.get('current_project')
    if not project_id:
        return jsonify({'success': False, 'message': 'No project selected'}), 400
    
    saved = persistent_data['saved_videos'].get(project_id, {})
    
    # Handle backward compatibility
    if isinstance(saved, list):
        persistent_data['saved_videos'][project_id] = {"Uncategorized": saved} if saved else {}
        saved = persistent_data['saved_videos'][project_id]
    
    # Search and remove from all groups
    removed = False
    for group_name in list(saved.keys()):
        original_count = len(saved[group_name])
        saved[group_name] = [v for v in saved[group_name] if v['video_id'] != video_id]
        if len(saved[group_name]) < original_count:
            removed = True
        # Clean up empty groups
        if not saved[group_name]:
            del saved[group_name]
    
    if removed:
        save_persistent_data(persistent_data)
        return jsonify({'success': True, 'message': 'Video removed'})
    else:
        return jsonify({'success': False, 'message': 'Video not found'}), 404

# ============== MULTI-SELECT VIDEOS ==============

@app.route('/api/select-videos', methods=['POST'])
def api_select_videos():
    """Select multiple videos for script generation."""
    data = request.json
    video_ids = data.get('video_ids', [])
    
    # Find videos from either discovery results or saved videos
    selected = []
    all_videos = app_state['videos'] + persistent_data['saved_videos'].get(
        persistent_data.get('current_project', ''), []
    )
    
    for vid_id in video_ids:
        video = next((v for v in all_videos if v['video_id'] == vid_id), None)
        if video:
            selected.append(video)
    
    app_state['selected_videos'] = selected
    return jsonify({'success': True, 'selected': selected, 'count': len(selected)})

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5001))
    print(f"\n🎬 YouTube Niche Verifier starting...")
    print(f"📍 Open http://localhost:{port} in your browser\n")
    app.run(debug=True, port=port)
