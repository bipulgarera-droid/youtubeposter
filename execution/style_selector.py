"""
Style Selector - Select video style for AI image generation.

Provides options for different visual styles:
1. Cartoon (CFH style)
2. Painting (current default)
3. Documentary (stock-style)
4. Minimal (text-heavy)
"""

from typing import Dict, List, Tuple


# Style definitions with prompt modifiers
STYLES = {
    "cartoon": {
        "name": "Cartoon (Illustrated)",
        "description": "Semi-realistic cartoon illustration style. Characters with expressive faces, moody backgrounds.",
        "prompt_prefix": "Semi-realistic cartoon illustration style, ",
        "prompt_suffix": ", dark moody atmosphere, dramatic lighting, expressive character, illustrated art style",
        "thumbnail_style": "illustrated cartoon character with expressive emotion, dark moody background",
        "example": "Similar to Chill Financial Historian thumbnails"
    },
    "painting": {
        "name": "Digital Painting",
        "description": "Artistic digital painting style. Dramatic, cinematic feel.",
        "prompt_prefix": "Digital painting, artistic style, ",
        "prompt_suffix": ", dramatic cinematic lighting, detailed, masterpiece quality",
        "thumbnail_style": "dramatic digital painting with cinematic composition",
        "example": "Concept art style"
    },
    "documentary": {
        "name": "Documentary (Realistic)",
        "description": "Photo-realistic documentary style. Like stock footage stills.",
        "prompt_prefix": "Photo-realistic documentary style, ",
        "prompt_suffix": ", journalistic photography, high quality, professional",
        "thumbnail_style": "professional photography, documentary style",
        "example": "BBC/Netflix documentary aesthetic"
    },
    "minimal": {
        "name": "Minimal (Text-Focused)",
        "description": "Simple backgrounds with text overlays. Clean, modern.",
        "prompt_prefix": "Minimal clean background, ",
        "prompt_suffix": ", simple gradient, modern design, space for text overlay",
        "thumbnail_style": "clean minimal background with bold text",
        "example": "Modern infographic style"
    },
    "dark_editorial": {
        "name": "Dark Editorial",
        "description": "Dark, moody editorial style. Shadows, high contrast.",
        "prompt_prefix": "Dark moody editorial style, ",
        "prompt_suffix": ", high contrast, deep shadows, dramatic noir lighting, cinematic",
        "thumbnail_style": "dark editorial photography with dramatic shadows",
        "example": "Vice/The Economist visual style"
    }
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


def get_style_keyboard_options() -> List[Tuple[str, str]]:
    """Return (id, name) tuples for Telegram inline keyboard."""
    return [(style_id, style["name"]) for style_id, style in STYLES.items()]


def apply_style_to_prompt(base_prompt: str, style_id: str) -> str:
    """Apply style modifiers to a base image prompt."""
    style = STYLES.get(style_id, STYLES["cartoon"])
    
    return f"{style['prompt_prefix']}{base_prompt}{style['prompt_suffix']}"


def get_thumbnail_style_prompt(style_id: str) -> str:
    """Get thumbnail-specific style prompt."""
    style = STYLES.get(style_id, STYLES["cartoon"])
    return style["thumbnail_style"]


def get_style_by_id(style_id: str) -> Dict:
    """Get full style configuration by ID."""
    return STYLES.get(style_id, STYLES["cartoon"])


# Default style
DEFAULT_STYLE = "cartoon"


if __name__ == "__main__":
    # Test
    print("Available styles:")
    for opt in get_style_options():
        print(f"\n{opt['name']}")
        print(f"  {opt['description']}")
    
    print("\n\nTest prompt application:")
    base = "worried businessman looking at crumbling factory"
    for style_id in STYLES:
        styled = apply_style_to_prompt(base, style_id)
        print(f"\n{style_id}: {styled[:100]}...")
