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


def download_file(storage_path: str, local_path: str) -> bool:
    """
    Download a file from Supabase storage.
    
    Args:
        storage_path: Path in storage (e.g., 'job_id/images/chunk_001.png')
        local_path: Local path to save file
    
    Returns:
        True if successful
    """
    client = get_client()
    if not client:
        return False
    
    try:
        # Ensure local directory exists
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        
        # Download
        response = client.storage.from_(BUCKET_NAME).download(storage_path)
        
        with open(local_path, 'wb') as f:
            f.write(response)
        
        print(f"✅ Downloaded: {storage_path} → {local_path}")
        return True
        
    except Exception as e:
        print(f"❌ Download failed: {e}")
        return False


def list_all_jobs() -> list:
    """
    List all job folders in the bucket.
    
    Returns:
        List of job IDs (folder names) sorted by newest first
    """
    client = get_client()
    if not client:
        return []
    
    try:
        result = client.storage.from_(BUCKET_NAME).list()
        # Filter to only folders (jobs), not files
        jobs = [item['name'] for item in result if item.get('id') is None or item['name'].startswith('video_')]
        # Sort by name (which includes timestamp) - newest first
        jobs.sort(reverse=True)
        return jobs
    except Exception as e:
        print(f"❌ List jobs failed: {e}")
        return []


def get_job_assets(job_id: str) -> dict:
    """
    Get available assets for a job.
    
    Returns:
        dict with keys: images, script, video, subtitled_video, srt, state
        Each value is a list of file paths or None
    """
    client = get_client()
    if not client:
        return {}
    
    assets = {
        'images': [],
        'script': None,
        'video': None,
        'subtitled_video': None,
        'srt': None,
        'state': None
    }
    
    try:
        # List root level
        root_files = client.storage.from_(BUCKET_NAME).list(job_id)
        
        for item in root_files:
            name = item['name']
            
            if name == 'images':
                # List images folder - paginate to get all (Supabase default is 100)
                all_images = []
                offset = 0
                limit = 1000  # Max per request
                while True:
                    images = client.storage.from_(BUCKET_NAME).list(
                        f"{job_id}/images",
                        {"limit": limit, "offset": offset}
                    )
                    if not images:
                        break
                    all_images.extend(images)
                    if len(images) < limit:
                        break
                    offset += limit
                
                assets['images'] = [f"{job_id}/images/{img['name']}" for img in all_images if img['name'].endswith('.png')]
                assets['images'].sort()
            elif name == 'script':
                scripts = client.storage.from_(BUCKET_NAME).list(f"{job_id}/script")
                if scripts:
                    assets['script'] = f"{job_id}/script/{scripts[0]['name']}"
            elif name == 'video':
                videos = client.storage.from_(BUCKET_NAME).list(f"{job_id}/video")
                for v in videos:
                    if v['name'].endswith('_subtitled.mp4'):
                        assets['subtitled_video'] = f"{job_id}/video/{v['name']}"
                    elif v['name'].endswith('.mp4'):
                        assets['video'] = f"{job_id}/video/{v['name']}"
                    elif v['name'].endswith('.srt'):
                        assets['srt'] = f"{job_id}/video/{v['name']}"
            elif name == 'state.json':
                assets['state'] = f"{job_id}/state.json"
    
    except Exception as e:
        print(f"❌ Get job assets failed: {e}")
    
    return assets


def get_latest_job_with_assets() -> tuple:
    """
    Find the most recent job that has any assets.
    
    Returns:
        (job_id, assets_dict) or (None, {})
    """
    jobs = list_all_jobs()
    
    for job_id in jobs:
        if job_id.startswith('test_'):
            continue  # Skip test uploads
        assets = get_job_assets(job_id)
        if assets.get('images') or assets.get('video') or assets.get('subtitled_video'):
            return (job_id, assets)
    
    return (None, {})


def cleanup_old_jobs(keep_count: int = 3) -> int:
    """
    Delete old jobs, keeping the most recent ones.
    
    Args:
        keep_count: Number of recent jobs to keep
    
    Returns:
        Number of jobs deleted
    """
    jobs = list_all_jobs()
    
    # Filter out test jobs
    real_jobs = [j for j in jobs if not j.startswith('test_')]
    
    if len(real_jobs) <= keep_count:
        return 0
    
    # Delete old jobs
    jobs_to_delete = real_jobs[keep_count:]
    deleted = 0
    
    for job_id in jobs_to_delete:
        if delete_job_folder(job_id):
            deleted += 1
            print(f"🗑️ Deleted old job: {job_id}")
    
    return deleted


def delete_job_folder(job_id: str) -> bool:
    """Delete an entire job folder recursively."""
    client = get_client()
    if not client:
        return False
    
    try:
        assets = get_job_assets(job_id)
        all_paths = []
        
        # Collect all file paths
        if assets.get('images'):
            all_paths.extend(assets['images'])
        if assets.get('script'):
            all_paths.append(assets['script'])
        if assets.get('video'):
            all_paths.append(assets['video'])
        if assets.get('subtitled_video'):
            all_paths.append(assets['subtitled_video'])
        if assets.get('srt'):
            all_paths.append(assets['srt'])
        if assets.get('state'):
            all_paths.append(assets['state'])
        
        if all_paths:
            client.storage.from_(BUCKET_NAME).remove(all_paths)
        
        return True
    except Exception as e:
        print(f"❌ Delete job folder failed: {e}")
        return False


def upload_state(job_id: str, state: dict) -> Optional[str]:
    """Upload pipeline state for recovery."""
    return upload_json(state, job_id, '', 'state.json')


def download_state(job_id: str) -> Optional[dict]:
    """Download pipeline state for recovery."""
    client = get_client()
    if not client:
        return None
    
    try:
        response = client.storage.from_(BUCKET_NAME).download(f"{job_id}/state.json")
        return json.loads(response.decode('utf-8'))
    except Exception as e:
        print(f"❌ Download state failed: {e}")
        return None


if __name__ == "__main__":
    # Test
    print("Testing Supabase storage...")
    
    if get_client():
        url = upload_text("Hello World - Test", "test_job_123", "test", "hello.txt")
        print(f"Test upload: {url}")
        
        # Test list jobs
        print(f"\nJobs in bucket: {list_all_jobs()}")
    else:
        print("Supabase not configured")
