#!/usr/bin/env python3
"""
Job Queue System for background video generation.
Uses Redis Queue (RQ) for async job processing.
"""
import os
import json
import uuid
from datetime import datetime
from typing import Optional, Dict, Any
from redis import Redis
from rq import Queue
from dotenv import load_dotenv

load_dotenv()

# Redis connection
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379')

def get_redis_connection():
    """Get Redis connection from URL."""
    return Redis.from_url(REDIS_URL)

def get_queue(name: str = 'default'):
    """Get a queue by name."""
    return Queue(name, connection=get_redis_connection())

# Job status tracking (stored in Redis)
class JobStatus:
    PENDING = 'pending'
    RUNNING = 'running'
    COMPLETED = 'completed'
    FAILED = 'failed'

def create_job_id() -> str:
    """Create a unique job ID."""
    return f"job_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"

def set_job_status(job_id: str, status: str, progress: int = 0, 
                   message: str = "", result: Optional[Dict] = None):
    """Update job status in Redis."""
    redis = get_redis_connection()
    job_data = {
        'job_id': job_id,
        'status': status,
        'progress': progress,
        'message': message,
        'result': result,
        'updated_at': datetime.now().isoformat()
    }
    redis.set(f"job_status:{job_id}", json.dumps(job_data), ex=86400)  # 24h expiry

def get_job_status(job_id: str) -> Optional[Dict]:
    """Get job status from Redis."""
    redis = get_redis_connection()
    data = redis.get(f"job_status:{job_id}")
    if data:
        return json.loads(data)
    return None


def cancel_job(job_id: str) -> bool:
    """Cancel a queued or running job."""
    try:
        from rq.job import Job
        redis = get_redis_connection()
        
        # Try to find and cancel the RQ job
        for queue_name in ['high', 'default', 'low']:
            queue = get_queue(queue_name)
            for job in queue.jobs:
                if job_id in str(job.args) or job_id in str(job.kwargs):
                    job.cancel()
                    set_job_status(job_id, JobStatus.FAILED, 0, "Job cancelled by user")
                    return True
        
        # If job is running, mark it as cancelled (worker will check)
        status = get_job_status(job_id)
        if status and status['status'] in ['pending', 'running']:
            set_job_status(job_id, JobStatus.FAILED, 0, "Job cancelled by user")
            return True
        
        return False
    except Exception as e:
        print(f"Error cancelling job: {e}")
        return False

def queue_full_pipeline(youtube_url: str, topic: Optional[str] = None,
                        telegram_chat_id: Optional[int] = None) -> str:
    """
    Queue a full pipeline job for background processing.
    
    Args:
        youtube_url: YouTube video URL to use as reference
        topic: Optional topic override (defaults to video title)
        telegram_chat_id: Optional Telegram chat ID for notifications
    
    Returns:
        Job ID for tracking
    """
    from execution.full_pipeline import run_full_pipeline
    
    job_id = create_job_id()
    queue = get_queue('default')
    
    # Set initial status
    set_job_status(job_id, JobStatus.PENDING, 0, "Job queued, waiting to start...")
    
    # Queue the job
    queue.enqueue(
        run_full_pipeline,
        job_id=job_id,
        youtube_url=youtube_url,
        topic=topic,
        telegram_chat_id=telegram_chat_id,
        job_timeout='30m',  # 30 minute timeout
        result_ttl=86400,   # Keep result for 24h
        failure_ttl=86400
    )
    
    return job_id

def queue_news_pipeline(news_url: str, topic: str,
                        telegram_chat_id: Optional[int] = None) -> str:
    """
    Queue a news-based pipeline job.
    
    Args:
        news_url: News article URL for deep research
        topic: Topic for the video
        telegram_chat_id: Optional Telegram chat ID for notifications
    
    Returns:
        Job ID for tracking
    """
    from execution.full_pipeline import run_news_pipeline
    
    job_id = create_job_id()
    queue = get_queue('default')
    
    set_job_status(job_id, JobStatus.PENDING, 0, "News pipeline queued...")
    
    queue.enqueue(
        run_news_pipeline,
        job_id=job_id,
        news_url=news_url,
        topic=topic,
        telegram_chat_id=telegram_chat_id,
        job_timeout='30m',
        result_ttl=86400,
        failure_ttl=86400
    )
    
    return job_id
