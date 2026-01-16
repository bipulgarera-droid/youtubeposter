#!/usr/bin/env python3
"""
Video Generation Module
Combines audio chunks + screenshots into video segments, then assembles final video.
Uses FFmpeg for video processing.
"""

import os
import subprocess
import json
from pathlib import Path
from typing import Optional, List, Dict

# Add Homebrew bin to PATH to ensure FFmpeg is found
os.environ["PATH"] += os.pathsep + "/opt/homebrew/bin"


# Paths
TMP_DIR = Path(__file__).parent.parent / '.tmp'
SCREENSHOTS_DIR = TMP_DIR / 'screenshots'
AUDIO_DIR = TMP_DIR / 'audio'
VIDEO_DIR = TMP_DIR / 'video_segments'
OUTPUT_DIR = TMP_DIR / 'final_videos'  # Changed from 'output' to 'final_videos'

# Video settings
VIDEO_WIDTH = 1920
VIDEO_HEIGHT = 1080
VIDEO_FPS = 30
PLACEHOLDER_COLOR = "0x1a1a2e"  # Dark blue-gray


def ensure_directories():
    """Ensure all required directories exist."""
    for d in [SCREENSHOTS_DIR, AUDIO_DIR, VIDEO_DIR, OUTPUT_DIR]:
        d.mkdir(parents=True, exist_ok=True)


def check_ffmpeg() -> bool:
    """Check if FFmpeg is installed."""
    try:
        result = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True)
        return result.returncode == 0
    except FileNotFoundError:
        return False


def get_audio_duration(audio_path: str) -> float:
    """Get duration of audio file in seconds using FFprobe."""
    try:
        result = subprocess.run([
            'ffprobe', '-i', audio_path,
            '-show_entries', 'format=duration',
            '-v', 'quiet', '-of', 'csv=p=0'
        ], capture_output=True, text=True)
        return float(result.stdout.strip())
    except Exception as e:
        print(f"Error getting audio duration: {e}")
        return 0.0


def create_placeholder_image(output_path: str, text: str = "") -> bool:
    """Create a placeholder image for chunks without screenshots."""
    try:
        # Create a solid color image with optional text overlay
        cmd = [
            'ffmpeg', '-y',
            '-f', 'lavfi',
            '-i', f'color=c={PLACEHOLDER_COLOR}:s={VIDEO_WIDTH}x{VIDEO_HEIGHT}:d=1',
            '-vframes', '1',
            output_path
        ]
        
        if text:
            # Escape special characters for FFmpeg drawtext filter
            escaped_text = text[:50].replace("\\", "\\\\").replace("'", "'\\''").replace(":", "\\:")
            # Add text overlay (simplified - just center text)
            cmd = [
                'ffmpeg', '-y',
                '-f', 'lavfi',
                '-i', f'color=c={PLACEHOLDER_COLOR}:s={VIDEO_WIDTH}x{VIDEO_HEIGHT}:d=1',
                '-vf', f"drawtext=text='{escaped_text}':fontcolor=white:fontsize=32:x=(w-text_w)/2:y=(h-text_h)/2",
                '-vframes', '1',
                output_path
            ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.returncode == 0
    except Exception as e:
        print(f"Error creating placeholder: {e}")
        return False


def resize_image_for_video(input_path: str, output_path: str) -> bool:
    """Resize and CENTER-CROP image to fill video dimensions (16:9). No black bars."""
    try:
        # Scale to cover the entire frame, then center-crop to exact dimensions
        # force_original_aspect_ratio=increase scales up to fill
        # crop=w:h centers the crop
        cmd = [
            'ffmpeg', '-y',
            '-i', input_path,
            '-vf', f'scale={VIDEO_WIDTH}:{VIDEO_HEIGHT}:force_original_aspect_ratio=increase,crop={VIDEO_WIDTH}:{VIDEO_HEIGHT}',
            '-frames:v', '1',
            output_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.returncode == 0
    except Exception as e:
        print(f"Error resizing image: {e}")
        return False


def create_video_segment(
    chunk_id: int,
    audio_path: str,
    screenshot_path: Optional[str],
    chunk_text: str = "",
    stock_video_path: Optional[str] = None
) -> Optional[str]:
    """
    Create a single video segment from audio + screenshot (or stock video).
    If stock_video_path is provided, uses that instead of the static screenshot.
    Returns path to output segment or None if failed.
    """
    ensure_directories()
    
    if not os.path.exists(audio_path):
        print(f"  ❌ Audio not found: {audio_path}")
        return None
    
    # Get audio duration
    duration = get_audio_duration(audio_path)
    if duration <= 0:
        print(f"  ❌ Could not determine audio duration")
        return None
    
    output_path = str(VIDEO_DIR / f'segment_{chunk_id:04d}.mp4')
    
    # Use custom/stock video if provided and exists
    # NOTE: For now, only custom uploaded videos work reliably
    if stock_video_path and os.path.exists(stock_video_path):
        print(f"  🎬 Using stock video: {os.path.basename(stock_video_path)}")
        try:
            # Use stock video: loop it to match audio duration, overlay audio
            cmd = [
                'ffmpeg', '-y',
                '-fflags', '+genpts',  # Generate fresh timestamps
                '-stream_loop', '-1',  # Loop video infinitely
                '-i', stock_video_path,
                '-i', audio_path,
                '-map', '0:v',  # Video from stock video
                '-map', '1:a',  # Audio from audio file
                '-c:v', 'libx264',
                '-preset', 'veryfast',  # Much faster (was 'slow')
                '-crf', '23',  # Slightly lower quality but faster (was 18)
                '-profile:v', 'high',  # QuickTime compatible
                '-level', '4.0',
                '-r', '30',  # Force constant 30fps
                '-vsync', 'cfr',  # Constant frame rate sync
                '-vf', f'scale={VIDEO_WIDTH}:{VIDEO_HEIGHT}:force_original_aspect_ratio=decrease,pad={VIDEO_WIDTH}:{VIDEO_HEIGHT}:(ow-iw)/2:(oh-ih)/2',
                '-c:a', 'aac',
                '-b:a', '192k',
                '-af', f'apad=whole_dur={duration}',  # Pad audio to exact duration
                '-pix_fmt', 'yuv420p',
                '-t', str(duration),  # Cut at exact audio duration
                output_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                # Verify the segment was created with correct duration
                segment_duration = get_audio_duration(output_path)  # Works on video too
                print(f"  ✅ Video segment created: {segment_duration:.2f}s (target: {duration:.2f}s)")
                return output_path
            else:
                print(f"  ⚠️ Stock video failed, falling back to screenshot: {result.stderr[:200]}")
                # Fall through to screenshot logic
        except Exception as e:
            print(f"  ⚠️ Stock video error, falling back: {e}")
            # Fall through to screenshot logic
    
    # Standard path: use screenshot or placeholder
    temp_image = str(VIDEO_DIR / f'temp_img_{chunk_id}.png')
    
    if screenshot_path and os.path.exists(screenshot_path):
        # Resize existing screenshot
        if not resize_image_for_video(screenshot_path, temp_image):
            print(f"  ⚠️ Failed to resize image, using placeholder")
            create_placeholder_image(temp_image, chunk_text[:30])
    else:
        # Create placeholder
        create_placeholder_image(temp_image, chunk_text[:30] if chunk_text else "")
    
    print(f"  📷 Creating screenshot segment: target duration {duration:.2f}s")
    
    # Determine pan direction: 2 up, 2 down, repeat
    # Pattern: chunks 0-1 = up, chunks 2-3 = down, chunks 4-5 = up, etc.
    cycle_position = (chunk_id // 2) % 2  # 0 = up, 1 = down
    pan_direction = "up" if cycle_position == 0 else "down"
    
    # Calculate zoompan parameters for SMOOTH and CONSISTENT panning
    # Use higher internal fps for smooth interpolation
    internal_fps = 60  # Higher fps for smoother motion
    total_frames = int(duration * internal_fps)
    zoom = 1.15  # More noticeable movement while staying smooth
    
    # FIXED pan speed: complete the pan in a consistent time period
    # This ensures pan speed looks the same regardless of audio duration
    # Longer clips = more of the pan is shown, shorter clips = less, but SAME speed
    pan_duration = 8.0  # Pan takes 8 seconds to complete full travel
    pan_frames = int(pan_duration * internal_fps)
    
    # Calculate how much of the pan to show based on actual duration
    # If duration < pan_duration, we only show a portion of the pan
    pan_progress = f"min(on/{pan_frames}, 1)"  # Clamps at 1.0 when complete
    
    # Use smooth linear interpolation for y position
    if pan_direction == "up":
        # Start at bottom, move to top smoothly  
        y_expr = f"(ih*(1-1/zoom))*(1-{pan_progress})"
        direction_icon = "⬆️"
    else:
        # Start at top, move to bottom smoothly  
        y_expr = f"(ih*(1-1/zoom))*({pan_progress})"
        direction_icon = "⬇️"
    
    print(f"  {direction_icon} Pan direction: {pan_direction}")
    
    try:
        # Create segment with SMOOTH Ken Burns pan effect
        # zoompan at 60fps internally, then output at 30fps for smooth motion
        vf_filter = (
            f"scale=8000:-1,"  # Scale up image first for quality
            f"zoompan=z={zoom}:x='(iw-iw/zoom)/2':y='{y_expr}':"
            f"d={total_frames}:s={VIDEO_WIDTH}x{VIDEO_HEIGHT}:fps={internal_fps},"
            f"fps={30}"  # Output at 30fps
        )
        
        cmd = [
            'ffmpeg', '-y',
            '-loop', '1',
            '-i', temp_image,
            '-i', audio_path,
            '-vf', vf_filter,
            '-c:v', 'libx264',
            '-preset', 'slow',
            '-crf', '18',
            '-r', '30',
            '-vsync', 'cfr',
            '-b:v', '8M',
            '-maxrate', '10M',
            '-bufsize', '16M',
            '-c:a', 'aac',
            '-b:a', '192k',
            '-pix_fmt', 'yuv420p',
            '-t', str(duration),
            output_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            # Verify segment duration
            segment_duration = get_audio_duration(output_path)
            print(f"  ✅ Screenshot segment created: {segment_duration:.2f}s (target: {duration:.2f}s)")
            # Clean up temp image
            if os.path.exists(temp_image):
                os.remove(temp_image)
            return output_path
        else:
            print(f"  ❌ FFmpeg error: {result.stderr[:200]}")
            return None
            
    except Exception as e:
        print(f"  ❌ Error creating segment: {e}")
        return None


def concatenate_segments(segment_paths: List[str], output_path: str) -> bool:
    """Concatenate all video segments into final video."""
    if not segment_paths:
        print("No segments to concatenate")
        return False
    
    ensure_directories()
    
    print(f"\n📹 Concatenating {len(segment_paths)} segments...")
    
    # Verify all segments exist and show their durations
    for i, path in enumerate(segment_paths):
        if os.path.exists(path):
            duration = get_audio_duration(path)
            print(f"   {i}: {os.path.basename(path)} ({duration:.2f}s)")
        else:
            print(f"   {i}: ⚠️ MISSING: {path}")
    
    # Create concat file
    concat_file = str(VIDEO_DIR / 'concat_list.txt')
    with open(concat_file, 'w') as f:
        for path in segment_paths:
            # FFmpeg concat requires escaped paths
            escaped_path = path.replace("'", "'\\''")
            f.write(f"file '{escaped_path}'\n")
    
    try:
        # Re-encode during concatenation to ensure consistent timing
        # Use fast preset for speed, baseline profile for QuickTime compatibility
        cmd = [
            'ffmpeg', '-y',
            '-f', 'concat',
            '-safe', '0',
            '-i', concat_file,
            '-c:v', 'libx264',
            '-preset', 'veryfast',  # Much faster than 'medium'
            '-crf', '23',  # Slightly lower quality but faster (was 18)
            '-profile:v', 'high',  # QuickTime compatible
            '-level', '4.0',  # Widely compatible level
            '-r', '30',  # Force 30fps output
            '-vsync', 'cfr',  # Constant frame rate
            '-c:a', 'aac',
            '-b:a', '192k',
            '-af', 'aresample=async=1',  # Resample audio to fix timing
            '-pix_fmt', 'yuv420p',
            '-movflags', '+faststart',
            output_path
        ]
        
        print(f"   Re-encoding final video...")
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        # Clean up concat file
        if os.path.exists(concat_file):
            os.remove(concat_file)
        
        if result.returncode == 0:
            # Verify final duration
            final_duration = get_audio_duration(output_path)
            print(f"   ✅ Final video: {final_duration:.2f}s")
        
        return result.returncode == 0
        
    except Exception as e:
        print(f"Error concatenating: {e}")
        return False


def build_video_from_chunks(chunks: List[Dict], progress_callback=None) -> Dict:
    """
    Build complete video from chunk data.
    
    Each chunk should have:
    - id: int
    - text: str
    - audio_path: str (path to MP3)
    - screenshot_path: str or None (path to screenshot)
    
    Args:
        progress_callback: Optional callable that takes (current, total, message) for progress updates
    
    Returns dict with success status and output path.
    """
    if not check_ffmpeg():
        return {
            'success': False,
            'message': 'FFmpeg is not installed. Please install FFmpeg to generate videos.',
            'output_path': None
        }
    
    ensure_directories()
    
    print(f"\n{'='*60}")
    print(f"VIDEO GENERATION")
    print(f"Processing {len(chunks)} chunks...")
    print(f"{'='*60}\n")
    
    segment_paths = []
    errors = []
    
    for i, chunk in enumerate(chunks):
        chunk_id = chunk.get('id', i)
        text = chunk.get('text', '')
        audio_path = chunk.get('audio_path', '')
        screenshot_path = chunk.get('screenshot_path')
        stock_video_path = chunk.get('stock_video_path')  # Stock video if selected
        
        print(f"  [{i+1}/{len(chunks)}] Processing chunk {chunk_id}...")
        
        # Progress callback every 20 segments
        if progress_callback and (i + 1) % 20 == 0:
            try:
                progress_callback(i + 1, len(chunks), f"⏳ Assembling video: {i + 1}/{len(chunks)} segments...")
            except Exception as e:
                print(f"Progress callback error: {e}")
        
        segment_path = create_video_segment(
            chunk_id=chunk_id,
            audio_path=audio_path,
            screenshot_path=screenshot_path,
            chunk_text=text,
            stock_video_path=stock_video_path
        )
        
        if segment_path:
            segment_paths.append(segment_path)
            status = "✅" if screenshot_path and os.path.exists(screenshot_path) else "⚠️ (placeholder)"
            print(f"      {status} Created segment")
        else:
            errors.append(f"Chunk {chunk_id}")
            print(f"      ❌ Failed")
    
    if not segment_paths:
        return {
            'success': False,
            'message': 'No video segments were created',
            'output_path': None
        }
    
    # Concatenate all segments - use timestamp for unique filenames
    from datetime import datetime
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_path = str(OUTPUT_DIR / f'video_{timestamp}.mp4')
    print(f"\nConcatenating {len(segment_paths)} segments...")
    
    if concatenate_segments(segment_paths, output_path):
        # Get final video duration
        duration = get_audio_duration(output_path)
        
        print(f"\n✅ Video generated successfully!")
        print(f"   Path: {output_path}")
        print(f"   Duration: {duration:.1f}s ({duration/60:.1f} min)")
        
        return {
            'success': True,
            'message': f'Video generated: {len(segment_paths)} segments, {duration:.1f}s total',
            'output_path': output_path,
            'duration': duration,
            'segments_count': len(segment_paths),
            'errors': errors
        }
    else:
        return {
            'success': False,
            'message': 'Failed to concatenate video segments',
            'output_path': None
        }


def cleanup_segments():
    """Remove temporary video segments."""
    for f in VIDEO_DIR.glob('segment_*.mp4'):
        try:
            os.remove(f)
        except:
            pass
    for f in VIDEO_DIR.glob('temp_img_*.png'):
        try:
            os.remove(f)
        except:
            pass


if __name__ == '__main__':
    # Test FFmpeg availability
    if check_ffmpeg():
        print("✅ FFmpeg is installed")
    else:
        print("❌ FFmpeg is NOT installed")
        print("   Install with: brew install ffmpeg (macOS)")
