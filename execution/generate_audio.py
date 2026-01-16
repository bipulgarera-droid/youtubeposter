"""
Audio Generation - Generate TTS audio for video scripts.

Uses Google Cloud TTS Chirp 3 HD via the Gemini API key.
"""

import os
import re
import base64
import requests
from pathlib import Path
from typing import Optional


def generate_audio_from_script(
    script: str,
    output_path: str,
    voice: str = "en-US-Chirp3-HD-Charon"
) -> dict:
    """
    Generate audio file from script text using Google Cloud TTS.
    
    Args:
        script: Full script text to convert to speech
        output_path: Path to save the audio file (.wav)
        voice: TTS voice to use
    
    Returns:
        dict with success status and file path
    """
    gemini_api_key = os.getenv('GEMINI_API_KEY')
    if not gemini_api_key:
        return {"success": False, "error": "GEMINI_API_KEY not configured"}
    
    # Clean text for TTS
    clean_text = re.sub(r'https?://\S+', '', script)  # Remove URLs
    clean_text = re.sub(r'\n+', ' ', clean_text)      # Replace newlines
    clean_text = clean_text.strip()
    
    if not clean_text:
        return {"success": False, "error": "No speakable text after cleaning"}
    
    # Google Cloud TTS API endpoint
    tts_url = f"https://texttospeech.googleapis.com/v1beta1/text:synthesize?key={gemini_api_key}"
    
    # Request body for Chirp 3 HD
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
            "name": voice
        }
    }
    
    try:
        response = requests.post(
            tts_url,
            headers={'Content-Type': 'application/json'},
            json=tts_payload,
            timeout=120  # Longer timeout for full scripts
        )
        
        if response.status_code != 200:
            error_msg = response.json().get('error', {}).get('message', 'Unknown error')
            return {"success": False, "error": f"TTS API error: {error_msg}"}
        
        result = response.json()
        audio_content = result.get('audioContent', '')
        
        if not audio_content:
            return {"success": False, "error": "No audio content returned"}
        
        # Decode base64 audio and save
        audio_bytes = base64.b64decode(audio_content)
        
        # Ensure directory exists
        output_dir = Path(output_path).parent
        output_dir.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'wb') as f:
            f.write(audio_bytes)
        
        # Estimate duration
        word_count = len(clean_text.split())
        duration_estimate = word_count / 2.5  # ~150 wpm
        
        return {
            "success": True,
            "path": output_path,
            "duration_estimate": duration_estimate,
            "word_count": word_count
        }
        
    except requests.exceptions.Timeout:
        return {"success": False, "error": "TTS API timeout"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def generate_chunk_audio(
    chunk_text: str,
    output_path: str,
    chunk_index: int = 0
) -> dict:
    """
    Generate audio for a single script chunk.
    
    Args:
        chunk_text: Text for this chunk
        output_path: Path to save audio file
        chunk_index: Index of chunk (for logging)
    
    Returns:
        dict with success status and path
    """
    result = generate_audio_from_script(chunk_text, output_path)
    
    if result.get("success"):
        print(f"✅ Generated audio for chunk {chunk_index}")
    else:
        print(f"❌ Failed chunk {chunk_index}: {result.get('error')}")
    
    return result


def generate_all_audio(
    script: str,
    output_dir: str,
    chunks: Optional[list] = None
) -> dict:
    """
    Generate audio for all chunks in a script.
    
    Args:
        script: Full script text
        output_dir: Directory to save audio files
        chunks: Optional pre-split chunks (from generate_ai_images)
    
    Returns:
        dict with results for each chunk
    """
    from execution.generate_ai_images import split_script_to_chunks
    
    if chunks is None:
        chunks = split_script_to_chunks(script)
    
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    results = {
        "success": True,
        "total_chunks": len(chunks),
        "successful": 0,
        "failed": 0,
        "audio_files": []
    }
    
    for i, chunk in enumerate(chunks):
        audio_path = output_path / f"chunk_{i:03d}.wav"
        result = generate_chunk_audio(chunk, str(audio_path), i)
        
        if result.get("success"):
            results["successful"] += 1
            results["audio_files"].append({
                "index": i,
                "path": str(audio_path),
                "duration": result.get("duration_estimate", 0)
            })
        else:
            results["failed"] += 1
    
    results["success"] = results["failed"] == 0
    return results


if __name__ == "__main__":
    # Test with minimal text
    print("Testing audio generation...")
    
    test_text = "This is a test of the text to speech system."
    result = generate_audio_from_script(test_text, ".tmp/test_audio.wav")
    
    if result.get("success"):
        print(f"✅ Audio generated: {result['path']}")
        print(f"   Duration estimate: {result['duration_estimate']:.1f}s")
    else:
        print(f"❌ Failed: {result.get('error')}")
