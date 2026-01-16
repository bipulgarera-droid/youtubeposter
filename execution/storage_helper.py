#!/usr/bin/env python3
"""
Supabase Storage Helper for YouTube Pipeline.
Uploads intermediate files and returns public URLs.
"""
import os
import json
from pathlib import Path
from typing import Optional
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# Try to import supabase - install if not available
try:
    from supabase import create_client, Client
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False
    print("⚠️ Supabase not installed. Run: pip install supabase")

SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_ANON_KEY') or os.getenv('SUPABASE_SERVICE_KEY')
BUCKET_NAME = 'youtube-pipeline'


def get_client() -> Optional['Client']:
    """Get Supabase client."""
    if not SUPABASE_AVAILABLE:
        return None
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("⚠️ SUPABASE_URL or SUPABASE_ANON_KEY not set")
        return None
    return create_client(SUPABASE_URL, SUPABASE_KEY)


def upload_file(
    local_path: str,
    job_id: str,
    step_name: str,
    filename: str = None
) -> Optional[str]:
    """
    Upload a file to Supabase storage.
    
    Args:
        local_path: Path to local file
        job_id: Job ID for organizing files
        step_name: Step name (e.g., 'script', 'images', 'audio')
        filename: Optional custom filename (otherwise uses original)
    
    Returns:
        Public URL or None if failed
    """
    client = get_client()
    if not client:
        print("⚠️ Cannot upload - Supabase not configured")
        return None
    
    if not os.path.exists(local_path):
        print(f"⚠️ File not found: {local_path}")
        return None
    
    # Generate storage path: job_id/step_name/filename
    if not filename:
        filename = os.path.basename(local_path)
    
    storage_path = f"{job_id}/{step_name}/{filename}"
    
    try:
        with open(local_path, 'rb') as f:
            file_data = f.read()
        
        # Determine content type
        ext = Path(local_path).suffix.lower()
        content_types = {
            '.txt': 'text/plain',
            '.md': 'text/markdown',
            '.json': 'application/json',
            '.mp3': 'audio/mpeg',
            '.mp4': 'video/mp4',
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.srt': 'text/plain',
        }
        content_type = content_types.get(ext, 'application/octet-stream')
        
        # Upload
        result = client.storage.from_(BUCKET_NAME).upload(
            storage_path,
            file_data,
            file_options={"content-type": content_type}
        )
        
        # Get public URL
        public_url = client.storage.from_(BUCKET_NAME).get_public_url(storage_path)
        
        print(f"✅ Uploaded: {storage_path}")
        return public_url
        
    except Exception as e:
        print(f"❌ Upload failed: {e}")
        return None


def upload_text(
    text: str,
    job_id: str,
    step_name: str,
    filename: str
) -> Optional[str]:
    """
    Upload text content directly (without local file).
    
    Args:
        text: Text content to upload
        job_id: Job ID
        step_name: Step name
        filename: Filename with extension (e.g., 'script.txt')
    
    Returns:
        Public URL or None
    """
    client = get_client()
    if not client:
        return None
    
    storage_path = f"{job_id}/{step_name}/{filename}"
    
    try:
        result = client.storage.from_(BUCKET_NAME).upload(
            storage_path,
            text.encode('utf-8'),
            file_options={"content-type": "text/plain"}
        )
        
        public_url = client.storage.from_(BUCKET_NAME).get_public_url(storage_path)
        print(f"✅ Uploaded text: {storage_path}")
        return public_url
        
    except Exception as e:
        print(f"❌ Text upload failed: {e}")
        return None


def upload_json(
    data: dict,
    job_id: str,
    step_name: str,
    filename: str
) -> Optional[str]:
    """Upload JSON data."""
    return upload_text(json.dumps(data, indent=2), job_id, step_name, filename)


def list_job_files(job_id: str) -> list:
    """List all files for a job."""
    client = get_client()
    if not client:
        return []
    
    try:
        result = client.storage.from_(BUCKET_NAME).list(job_id)
        return result
    except:
        return []


def delete_job_files(job_id: str) -> bool:
    """Delete all files for a job."""
    client = get_client()
    if not client:
        return False
    
    try:
        files = list_job_files(job_id)
        if files:
            paths = [f"{job_id}/{f['name']}" for f in files]
            client.storage.from_(BUCKET_NAME).remove(paths)
        return True
    except Exception as e:
        print(f"❌ Delete failed: {e}")
        return False


if __name__ == "__main__":
    # Test
    print("Testing Supabase storage...")
    
    if get_client():
        url = upload_text("Hello World - Test", "test_job_123", "test", "hello.txt")
        print(f"Test upload: {url}")
    else:
        print("Supabase not configured")
