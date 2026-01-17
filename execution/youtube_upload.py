#!/usr/bin/env python3
"""
YouTube Upload Module
Handles OAuth 2.0 authentication and video upload to YouTube.
"""

import os
import json
import pickle
import base64
import tempfile
import logging
from pathlib import Path
from typing import Dict, Optional, List

# Set up logging
logger = logging.getLogger(__name__)

# Google API imports
try:
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import Flow
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    GOOGLE_API_AVAILABLE = True
except ImportError:
    GOOGLE_API_AVAILABLE = False
    print("⚠️ Google API libraries not installed. Run: pip install google-auth-oauthlib google-api-python-client")

# Redis for persistent token storage (Railway ephemeral filesystem)
try:
    from redis import Redis
    REDIS_URL = os.getenv('REDIS_URL')
    if REDIS_URL:
        redis_client = Redis.from_url(REDIS_URL)
        REDIS_AVAILABLE = True
        print(f"YouTube Upload: Redis connected to {REDIS_URL[:30]}...")
    else:
        # No REDIS_URL set - won't work on Railway
        REDIS_AVAILABLE = False
        redis_client = None
        print("YouTube Upload: REDIS_URL not set - credentials will not persist on Railway!")
except Exception as e:
    REDIS_AVAILABLE = False
    redis_client = None
    print(f"YouTube Upload: Redis connection failed: {e}")

# Paths
BASE_DIR = Path(__file__).parent.parent
CLIENT_SECRETS_FILE = BASE_DIR / 'client_secrets.json'
TOKEN_FILE = BASE_DIR / 'youtube_token.pickle'
REDIS_TOKEN_KEY = 'youtube_oauth_credentials'

# OAuth scopes for YouTube upload
SCOPES = ['https://www.googleapis.com/auth/youtube.upload']


def _get_client_config() -> Optional[Dict]:
    """Get client config from file or environment variable."""
    # First try file
    if CLIENT_SECRETS_FILE.exists():
        with open(CLIENT_SECRETS_FILE) as f:
            return json.load(f)
    
    # Then try environment variable
    env_secrets = os.environ.get('GOOGLE_CLIENT_SECRETS')
    if env_secrets:
        try:
            return json.loads(env_secrets)
        except json.JSONDecodeError:
            print("⚠️ GOOGLE_CLIENT_SECRETS env var is not valid JSON")
            return None
    
    return None


def _get_redirect_uri() -> str:
    """Get the appropriate redirect URI based on environment."""
    # Check if we're on Railway (has RAILWAY_STATIC_URL or similar)
    railway_url = os.environ.get('RAILWAY_PUBLIC_DOMAIN')
    if railway_url:
        return f"https://{railway_url}/oauth2callback"
    
    # Check for custom URL in env
    custom_url = os.environ.get('OAUTH_REDIRECT_URI')
    if custom_url:
        return custom_url
    
    # Default to localhost
    return 'http://localhost:5001/oauth2callback'


def check_dependencies() -> Dict:
    """Check if required dependencies are installed."""
    config = _get_client_config()
    return {
        'google_api_available': GOOGLE_API_AVAILABLE,
        'client_secrets_exists': config is not None,
        'token_exists': TOKEN_FILE.exists()
    }



def get_auth_url() -> Dict:
    """
    Generate OAuth authorization URL.
    User visits this URL to grant permission.
    """
    if not GOOGLE_API_AVAILABLE:
        return {'success': False, 'error': 'Google API libraries not installed'}
    
    client_config = _get_client_config()
    if not client_config:
        return {'success': False, 'error': 'client_secrets.json not found and GOOGLE_CLIENT_SECRETS env var not set'}
    
    redirect_uri = _get_redirect_uri()
    
    try:
        flow = Flow.from_client_config(
            client_config,
            scopes=SCOPES,
            redirect_uri=redirect_uri
        )
        
        auth_url, state = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            prompt='consent'
        )
        
        return {
            'success': True,
            'auth_url': auth_url,
            'state': state,
            'redirect_uri': redirect_uri
        }
    except Exception as e:
        return {'success': False, 'error': str(e)}


def handle_oauth_callback(authorization_response: str) -> Dict:
    """
    Handle the OAuth callback and save credentials.
    """
    logger.info("YouTube Auth: handle_oauth_callback called")
    
    if not GOOGLE_API_AVAILABLE:
        return {'success': False, 'error': 'Google API libraries not installed'}
    
    client_config = _get_client_config()
    if not client_config:
        return {'success': False, 'error': 'client_secrets.json not found and GOOGLE_CLIENT_SECRETS env var not set'}
    
    redirect_uri = _get_redirect_uri()
    logger.info(f"YouTube Auth: Using redirect_uri: {redirect_uri}")
    
    try:
        flow = Flow.from_client_config(
            client_config,
            scopes=SCOPES,
            redirect_uri=redirect_uri
        )
        
        flow.fetch_token(authorization_response=authorization_response)
        credentials = flow.credentials
        logger.info(f"YouTube Auth: Got credentials, valid={credentials.valid}")
        
        # Save credentials to pickle file (local)
        try:
            with open(TOKEN_FILE, 'wb') as token:
                pickle.dump(credentials, token)
            logger.info("YouTube Auth: Saved to pickle file")
        except Exception as e:
            logger.warning(f"YouTube Auth: Could not save to pickle file: {e}")
        
        # Also save to Redis for persistence on Railway
        logger.info(f"YouTube Auth: REDIS_AVAILABLE={REDIS_AVAILABLE}, redis_client={redis_client is not None}")
        if REDIS_AVAILABLE and redis_client:
            try:
                creds_data = pickle.dumps(credentials)
                creds_b64 = base64.b64encode(creds_data).decode('utf-8')
                redis_client.set(REDIS_TOKEN_KEY, creds_b64)
                logger.info(f"YouTube Auth: ✅ Credentials saved to Redis key '{REDIS_TOKEN_KEY}'")
            except Exception as e:
                logger.error(f"YouTube Auth: ❌ Could not save to Redis: {e}")
        else:
            logger.warning("YouTube Auth: Redis not available, credentials only saved locally")
        
        return {'success': True, 'message': 'YouTube authorization successful!'}
    except Exception as e:
        logger.error(f"YouTube Auth: OAuth callback error: {e}")
        return {'success': False, 'error': str(e)}


def get_credentials() -> Optional[Credentials]:
    """Load saved credentials from Redis (priority) or pickle file."""
    credentials = None
    
    # First try Redis (for Railway persistence)
    if REDIS_AVAILABLE and redis_client:
        try:
            creds_b64 = redis_client.get(REDIS_TOKEN_KEY)
            logger.info(f"YouTube Auth: Redis lookup for '{REDIS_TOKEN_KEY}': {'found' if creds_b64 else 'empty'}")
            if creds_b64:
                creds_data = base64.b64decode(creds_b64)
                credentials = pickle.loads(creds_data)
                logger.info(f"YouTube Auth: Credentials loaded from Redis, valid={credentials.valid if credentials else 'None'}")
                if credentials and credentials.valid:
                    return credentials
                # Return even if expired - might be refreshable
                if credentials:
                    return credentials
        except Exception as e:
            logger.warning(f"YouTube Auth: Could not load from Redis: {e}")
    else:
        logger.info(f"YouTube Auth: Redis not available (REDIS_AVAILABLE={REDIS_AVAILABLE})")
    
    # Fallback to pickle file
    if TOKEN_FILE.exists():
        try:
            logger.info(f"YouTube Auth: Loading from pickle file: {TOKEN_FILE}")
            with open(TOKEN_FILE, 'rb') as token:
                credentials = pickle.load(token)
                logger.info(f"YouTube Auth: Pickle credentials valid={credentials.valid if credentials else 'None'}")
                if credentials and credentials.valid:
                    return credentials
                return credentials
        except Exception as e:
            logger.warning(f"YouTube Auth: Pickle load failed: {e}")
    else:
        logger.info(f"YouTube Auth: Token pickle file does not exist at {TOKEN_FILE}")
    
    logger.info("YouTube Auth: No credentials found anywhere")
    return None


def is_authenticated() -> bool:
    """Check if we have valid credentials."""
    creds = get_credentials()
    result = creds is not None
    logger.info(f"YouTube Auth: is_authenticated() = {result}")
    return result


def upload_video(
    video_path: str,
    title: str,
    description: str,
    tags: List[str],
    privacy_status: str = 'private',
    thumbnail_path: str = None
) -> Dict:
    """
    Upload a video to YouTube.
    
    Args:
        video_path: Path to the video file
        title: Video title
        description: Video description
        tags: List of tags
        privacy_status: 'private', 'unlisted', or 'public'
        thumbnail_path: Optional path to thumbnail image
    
    Returns:
        Dict with success status and video ID or error
    """
    if not GOOGLE_API_AVAILABLE:
        return {'success': False, 'error': 'Google API libraries not installed'}
    
    credentials = get_credentials()
    if not credentials:
        return {'success': False, 'error': 'Not authenticated. Please authorize first.'}
    
    if not os.path.exists(video_path):
        return {'success': False, 'error': f'Video file not found: {video_path}'}
    
    try:
        # Build YouTube API client
        youtube = build('youtube', 'v3', credentials=credentials)
        
        # Video metadata
        body = {
            'snippet': {
                'title': title,
                'description': description,
                'tags': tags,
                'categoryId': '22'  # People & Blogs (common default)
            },
            'status': {
                'privacyStatus': privacy_status,
                'selfDeclaredMadeForKids': False
            }
        }
        
        # Upload video with smaller chunk size (256KB multiple) for better reliability
        # 256KB is minimum, but we'll try 512KB to balance speed/reliability
        chunk_size = 256 * 1024
        
        media = MediaFileUpload(
            video_path,
            chunksize=chunk_size, 
            resumable=True
        )
        
        print(f"Starting resumable upload for: {video_path} ({os.path.getsize(video_path)} bytes)")
        
        request = youtube.videos().insert(
            part='snippet,status',
            body=body,
            media_body=media
        )
        
        response = None
        error = None
        retry_count = 0
        max_retries = 10
        
        while response is None:
            try:
                status, response = request.next_chunk()
                if status:
                    progress = int(status.progress() * 100)
                    print(f"Upload progress: {progress}%")
            except Exception as e:
                # Handle retries with exponential backoff
                retry_count += 1
                if retry_count > max_retries:
                    raise e
                
                sleep_time = (2 ** retry_count) + (retry_count * 0.5)
                print(f"Upload error: {e}. Retrying in {sleep_time:.1f}s...")
                import time
                time.sleep(sleep_time)

        if response is not None and 'id' in response:
            video_id = response['id']
            video_url = f"https://www.youtube.com/watch?v={video_id}"
            print(f"Upload complete! Video ID: {video_id}")
            
            # Set custom thumbnail if provided
            if thumbnail_path and os.path.exists(thumbnail_path):
                try:
                    print(f"Uploading thumbnail: {thumbnail_path}")
                    youtube.thumbnails().set(
                        videoId=video_id,
                        media_body=MediaFileUpload(thumbnail_path)
                    ).execute()
                    print("Thumbnail set successfully")
                except Exception as e:
                    print(f"Warning: Failed to set thumbnail: {e}")
            
            return {
                'success': True,
                'video_id': video_id,
                'video_url': video_url,
                'message': f'Video uploaded successfully!'
            }
        else:
            return {'success': False, 'error': 'Upload completed but no video ID returned'}
        
    except Exception as e:
        print(f"Critical upload error: {e}")
        return {'success': False, 'error': str(e)}


def upload_captions(
    video_id: str,
    srt_path: str,
    language: str = 'en',
    name: str = 'English'
) -> Dict:
    """
    Upload SRT captions to a YouTube video.
    
    Args:
        video_id: YouTube video ID
        srt_path: Path to SRT file
        language: Language code (default 'en')
        name: Caption track name
    
    Returns:
        Dict with success status
    """
    if not GOOGLE_API_AVAILABLE:
        return {'success': False, 'error': 'Google API libraries not installed'}
    
    credentials = get_credentials()
    if not credentials:
        return {'success': False, 'error': 'Not authenticated'}
    
    if not os.path.exists(srt_path):
        return {'success': False, 'error': f'SRT file not found: {srt_path}'}
    
    try:
        youtube = build('youtube', 'v3', credentials=credentials)
        
        # Caption insert request
        body = {
            'snippet': {
                'videoId': video_id,
                'language': language,
                'name': name,
                'isDraft': False
            }
        }
        
        media = MediaFileUpload(srt_path, mimetype='application/x-subrip')
        
        print(f"📝 Uploading captions: {srt_path}")
        
        response = youtube.captions().insert(
            part='snippet',
            body=body,
            media_body=media
        ).execute()
        
        print(f"✅ Captions uploaded: {response.get('id')}")
        
        return {
            'success': True,
            'caption_id': response.get('id'),
            'message': 'Captions uploaded successfully'
        }
        
    except Exception as e:
        print(f"❌ Caption upload failed: {e}")
        return {'success': False, 'error': str(e)}


def upload_video_with_captions(
    video_path: str,
    title: str,
    description: str,
    tags: List[str],
    srt_path: str = None,
    thumbnail_path: str = None,
    privacy_status: str = 'private'
) -> Dict:
    """
    Upload video with thumbnail and captions in one call.
    
    Args:
        video_path: Path to video file
        title: Video title
        description: Video description (should include timestamps)
        tags: List of tags
        srt_path: Optional path to SRT for captions
        thumbnail_path: Optional path to thumbnail
        privacy_status: 'private', 'unlisted', or 'public'
    
    Returns:
        Dict with video_id, video_url, success status
    """
    # First upload the video
    result = upload_video(
        video_path=video_path,
        title=title,
        description=description,
        tags=tags,
        privacy_status=privacy_status,
        thumbnail_path=thumbnail_path
    )
    
    if not result.get('success'):
        return result
    
    video_id = result.get('video_id')
    
    # Upload captions if SRT provided
    if srt_path and os.path.exists(srt_path):
        caption_result = upload_captions(video_id, srt_path)
        result['captions_uploaded'] = caption_result.get('success', False)
        if not caption_result.get('success'):
            result['caption_error'] = caption_result.get('error')
    
    return result


if __name__ == '__main__':
    # Test
    status = check_dependencies()
    print(f"Dependencies: {status}")
    
    if status['client_secrets_exists']:
        result = get_auth_url()
        if result['success']:
            print(f"Auth URL: {result['auth_url']}")

