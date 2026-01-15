#!/usr/bin/env python3
"""
YouTube Upload Module
Handles OAuth 2.0 authentication and video upload to YouTube.
"""

import os
import json
import pickle
from pathlib import Path
from typing import Dict, Optional, List

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

# Paths
BASE_DIR = Path(__file__).parent.parent
CLIENT_SECRETS_FILE = BASE_DIR / 'client_secrets.json'
TOKEN_FILE = BASE_DIR / 'youtube_token.pickle'

# OAuth scopes for YouTube upload
SCOPES = ['https://www.googleapis.com/auth/youtube.upload']


def check_dependencies() -> Dict:
    """Check if required dependencies are installed."""
    return {
        'google_api_available': GOOGLE_API_AVAILABLE,
        'client_secrets_exists': CLIENT_SECRETS_FILE.exists(),
        'token_exists': TOKEN_FILE.exists()
    }


def get_auth_url() -> Dict:
    """
    Generate OAuth authorization URL.
    User visits this URL to grant permission.
    """
    if not GOOGLE_API_AVAILABLE:
        return {'success': False, 'error': 'Google API libraries not installed'}
    
    if not CLIENT_SECRETS_FILE.exists():
        return {'success': False, 'error': 'client_secrets.json not found'}
    
    try:
        flow = Flow.from_client_secrets_file(
            str(CLIENT_SECRETS_FILE),
            scopes=SCOPES,
            redirect_uri='http://localhost:5001/oauth2callback'
        )
        
        auth_url, state = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            prompt='consent'
        )
        
        return {
            'success': True,
            'auth_url': auth_url,
            'state': state
        }
    except Exception as e:
        return {'success': False, 'error': str(e)}


def handle_oauth_callback(authorization_response: str) -> Dict:
    """
    Handle the OAuth callback and save credentials.
    """
    if not GOOGLE_API_AVAILABLE:
        return {'success': False, 'error': 'Google API libraries not installed'}
    
    try:
        flow = Flow.from_client_secrets_file(
            str(CLIENT_SECRETS_FILE),
            scopes=SCOPES,
            redirect_uri='http://localhost:5001/oauth2callback'
        )
        
        flow.fetch_token(authorization_response=authorization_response)
        credentials = flow.credentials
        
        # Save credentials for future use
        with open(TOKEN_FILE, 'wb') as token:
            pickle.dump(credentials, token)
        
        return {'success': True, 'message': 'YouTube authorization successful!'}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def get_credentials() -> Optional[Credentials]:
    """Load saved credentials if they exist."""
    if not TOKEN_FILE.exists():
        return None
    
    try:
        with open(TOKEN_FILE, 'rb') as token:
            credentials = pickle.load(token)
            if credentials and credentials.valid:
                return credentials
            # Could add refresh logic here
            return credentials
    except:
        return None


def is_authenticated() -> bool:
    """Check if we have valid credentials."""
    creds = get_credentials()
    return creds is not None


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
        
    except Exception as e:
        return {'success': False, 'error': str(e)}


if __name__ == '__main__':
    # Test
    status = check_dependencies()
    print(f"Dependencies: {status}")
    
    if status['client_secrets_exists']:
        result = get_auth_url()
        if result['success']:
            print(f"Auth URL: {result['auth_url']}")
