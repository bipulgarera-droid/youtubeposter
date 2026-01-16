"""
Style Selector - Select video style for AI image generation.

Based on analysis of Chill Financial Historian videos:
- 2 Core Styles: Ghibli Cartoon and Impressionist Painting
- Mood variations within each style
- Text on images IS allowed (shop signs, in-world text)
- Characters and faces ARE allowed
"""

from typing import Dict, List, Tuple


# Core style definitions based on actual reference videos
STYLES = {
    "ghibli_cartoon": {
        "name": "Ghibli Cartoon (Primary)",
        "description": "Studio Ghibli-inspired animated style. Clean lines, expressive characters, detailed backgrounds. Used in 75% of videos.",
        "prompt_prefix": "Studio Ghibli style illustration, animated cartoon, ",
        "prompt_suffix": ", clean linework, expressive characters, detailed illustrated backgrounds, anime aesthetic, professional animation quality",
        "mood_options": ["bright_sunny", "dark_moody", "historical"],
        "allows_text": True,
        "allows_characters": True,
        "example": "Italian street scene, Venezuelan businessman, Victorian meeting room"
    },
    "impressionist_painting": {
        "name": "Impressionist Oil Painting",
        "description": "Classic French impressionist style. Oil painting aesthetic with visible brushstrokes. Muted color palette. Used for European/historical topics.",
        "prompt_prefix": "Impressionist oil painting style, like Renoir or Van Gogh, ",
        "prompt_suffix": ", visible brushstrokes, classic oil painting technique, muted warm color palette, traditional art gallery quality, fine art aesthetic",
        "mood_options": ["warm_nostalgic", "somber"],
        "allows_text": True,
        "allows_characters": True,
        "example": "French café scene, European workers, historical scenes"
    }
}


# Mood modifiers - applied on top of base style
MOODS = {
    "bright_sunny": {
        "name": "Bright & Sunny",
        "prompt_addition": "bright sunny day, vibrant colors, clear blue sky with fluffy white clouds, cheerful atmosphere, warm lighting",
        "use_for": "Positive scenes, establishing shots, 'La Dolce Vita' moments"
    },
    "dark_moody": {
        "name": "Dark & Moody", 
        "prompt_addition": "dark twilight atmosphere, moody lighting, night sky, dramatic shadows, melancholic mood, city lights in background",
        "use_for": "Economic collapse, crisis moments, sad character scenes"
    },
    "historical": {
        "name": "Historical/Period",
        "prompt_addition": "historical setting, period-appropriate details, warm candlelight or oil lamp lighting, antique furniture, rich wood tones",
        "use_for": "Past events, Victorian era, colonial history, meetings"
    },
    "warm_nostalgic": {
        "name": "Warm & Nostalgic",
        "prompt_addition": "warm sepia-tinted lighting, nostalgic atmosphere, golden hour sunlight, soft focus, romantic ambiance",
        "use_for": "European street scenes, café culture, 'old world' feel"
    },
    "somber": {
        "name": "Somber/Serious",
        "prompt_addition": "muted gray-blue color palette, overcast lighting, serious tone, workers and common people, realistic struggle",
        "use_for": "Poverty, working class, economic hardship"
    },
    "action_dramatic": {
        "name": "Action/Dramatic",
        "prompt_addition": "dramatic action scene, smoke and fire elements, military or conflict, tense atmosphere, epic scale composition",
        "use_for": "War scenes, invasions, conflicts, dramatic moments"
    }
}


# Scene types that determine composition
SCENE_TYPES = {
    "street_wide": "Wide establishing shot of a city street with buildings on both sides, people walking, perspective leading to center",
    "character_focus": "Close-up or medium shot focused on one or two expressive characters, emotion visible in face",
    "meeting_room": "Indoor scene with multiple people around a table, maps or documents visible, discussion happening",
    "landscape_vista": "Wide panoramic landscape view, epic scale, geographical features prominent",
    "construction_work": "Outdoor work scene with workers, machinery, construction or industrial activity"
}


def get_style_options() -> List[Dict]:
    """Return list of available styles for selection UI."""
    return [
        {
            "id": style_id,
            "name": style["name"],
            "description": style["description"],
            "example": style["example"]
        }
        for style_id, style in STYLES.items()
    ]


def get_mood_options(style_id: str = None) -> List[Dict]:
    """Return mood options, optionally filtered by style."""
    return [
        {
            "id": mood_id,
            "name": mood["name"],
            "use_for": mood["use_for"]
        }
        for mood_id, mood in MOODS.items()
    ]


def get_style_keyboard_options() -> List[Tuple[str, str]]:
    """Return (id, name) tuples for Telegram inline keyboard."""
    return [(style_id, style["name"]) for style_id, style in STYLES.items()]


def get_mood_keyboard_options() -> List[Tuple[str, str]]:
    """Return (id, name) tuples for mood selection."""
    return [(mood_id, mood["name"]) for mood_id, mood in MOODS.items()]


def apply_style_to_prompt(
    base_prompt: str, 
    style_id: str, 
    mood_id: str = None,
    scene_type: str = None
) -> str:
    """
    Apply style and mood modifiers to a base image prompt.
    
    Args:
        base_prompt: Core scene description
        style_id: 'ghibli_cartoon' or 'impressionist_painting'
        mood_id: Optional mood modifier
        scene_type: Optional scene composition type
    """
    style = STYLES.get(style_id, STYLES["ghibli_cartoon"])
    
    # Build prompt
    prompt_parts = [style["prompt_prefix"]]
    
    # Add scene type if specified
    if scene_type and scene_type in SCENE_TYPES:
        prompt_parts.append(SCENE_TYPES[scene_type] + ", ")
    
    # Add base prompt
    prompt_parts.append(base_prompt)
    
    # Add mood if specified
    if mood_id and mood_id in MOODS:
        prompt_parts.append(", " + MOODS[mood_id]["prompt_addition"])
    
    # Add style suffix
    prompt_parts.append(style["prompt_suffix"])
    
    return "".join(prompt_parts)


def get_thumbnail_style_prompt(style_id: str, mood_id: str = None) -> str:
    """Get thumbnail-specific style prompt."""
    style = STYLES.get(style_id, STYLES["ghibli_cartoon"])
    base = style["prompt_prefix"] + "dramatic thumbnail composition"
    
    if mood_id and mood_id in MOODS:
        base += ", " + MOODS[mood_id]["prompt_addition"]
    
    base += style["prompt_suffix"]
    return base


def get_style_by_id(style_id: str) -> Dict:
    """Get full style configuration by ID."""
    return STYLES.get(style_id, STYLES["ghibli_cartoon"])


def auto_select_mood(script_section: str) -> str:
    """
    Auto-select mood based on script content.
    
    Analyzes text to determine appropriate visual mood.
    """
    text_lower = script_section.lower()
    
    # Crisis/negative indicators
    if any(w in text_lower for w in ["collapse", "crisis", "death", "dying", "poor", "fail", "disaster"]):
        return "dark_moody"
    
    # Historical indicators  
    if any(w in text_lower for w in ["1970", "1980", "1900", "century", "historical", "colonial", "empire"]):
        return "historical"
    
    # War/conflict indicators
    if any(w in text_lower for w in ["war", "invasion", "military", "battle", "soldiers", "conflict"]):
        return "action_dramatic"
    
    # Nostalgic/European indicators
    if any(w in text_lower for w in ["café", "street", "europe", "paris", "italy", "france", "romantic"]):
        return "warm_nostalgic"
    
    # Default to bright for establishing shots
    return "bright_sunny"


def auto_select_scene_type(script_section: str) -> str:
    """Auto-select scene composition based on script content."""
    text_lower = script_section.lower()
    
    if any(w in text_lower for w in ["street", "city", "walk", "town"]):
        return "street_wide"
    
    if any(w in text_lower for w in ["he ", "she ", "person", "man", "woman", "worker"]):
        return "character_focus"
    
    if any(w in text_lower for w in ["meeting", "discuss", "table", "decision", "agreement"]):
        return "meeting_room"
    
    if any(w in text_lower for w in ["mountain", "ocean", "land", "geography", "map"]):
        return "landscape_vista"
    
    if any(w in text_lower for w in ["build", "construct", "factory", "mine", "work"]):
        return "construction_work"
    
    return "street_wide"  # Default


# Default style
DEFAULT_STYLE = "ghibli_cartoon"
DEFAULT_MOOD = "bright_sunny"


if __name__ == "__main__":
    # Test
    print("Available styles:")
    for opt in get_style_options():
        print(f"\n{opt['name']}")
        print(f"  {opt['description']}")
    
    print("\n\nTest prompt application:")
    base = "worried businessman sitting on a bench looking at a city skyline"
    
    styled = apply_style_to_prompt(base, "ghibli_cartoon", "dark_moody", "character_focus")
    print(f"\nGhibli + Dark Moody:\n{styled[:200]}...")
    
    styled2 = apply_style_to_prompt("French street with café", "impressionist_painting", "warm_nostalgic")
    print(f"\nImpressionist + Warm:\n{styled2[:200]}...")
