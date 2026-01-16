# Video Frame Style Guide

> Based on analysis of 8 Chill Financial Historian video frames.
> Use this directive when generating video images.

---

## 2 Core Styles

### 1. Ghibli Cartoon (Primary - 75% of videos)

**Reference:** Studio Ghibli animated films (Spirited Away, Howl's Moving Castle)

**Characteristics:**
- Clean illustrated linework
- Expressive cartoon characters with visible emotions
- Detailed backgrounds with depth
- Anime aesthetic without being "too anime"
- Characters have slightly exaggerated features

**When to use:**
- Most videos
- Any topic that needs characters
- Modern or historical scenes
- Street scenes, meeting rooms, landscapes

**Prompt keywords:**
```
Studio Ghibli style illustration, animated cartoon, clean linework, 
expressive characters, detailed illustrated backgrounds, anime aesthetic
```

---

### 2. Impressionist Oil Painting (25% of videos)

**Reference:** Renoir, Van Gogh, Monet

**Characteristics:**
- Visible brushstrokes
- Muted warm color palette (browns, creams, soft blues)
- Fine art gallery quality
- No hard outlines - soft blending
- Nostalgic "old world" feel

**When to use:**
- European topics (France, Italy)
- Historical/period content
- Working class/poverty scenes
- When you want a "museum painting" aesthetic

**Prompt keywords:**
```
Impressionist oil painting style, visible brushstrokes, 
classic oil painting technique, muted warm color palette, 
traditional art gallery quality
```

---

## 6 Mood Variations

| Mood | Description | Use For |
|------|-------------|---------|
| **Bright Sunny** | Blue sky, fluffy clouds, vibrant colors | Establishing shots, positive moments |
| **Dark Moody** | Twilight, city lights, melancholic | Crisis, collapse, sad character scenes |
| **Historical** | Candlelight, period details, antique | Past events, colonial, Victorian |
| **Warm Nostalgic** | Sepia tones, golden hour, romantic | European cafés, old-world charm |
| **Somber** | Gray-blue, overcast, serious | Poverty, hardship, struggle |
| **Action Dramatic** | Smoke, fire, epic scale | War, invasion, conflict |

---

## Scene Types

| Type | Composition |
|------|-------------|
| **Street Wide** | City street, buildings both sides, people walking, center perspective |
| **Character Focus** | Medium shot on 1-2 people, emotion visible |
| **Meeting Room** | Indoor, people around table, maps/documents |
| **Landscape Vista** | Wide panoramic, epic scale geography |
| **Construction Work** | Outdoor work scene, machinery, industrial |

---

## What's ALLOWED in Images

✅ **Characters and Faces** - Expressive characters are core to the style
✅ **Text on Buildings** - Shop signs, store names (can be gibberish)
✅ **Flags and Symbols** - Country flags, emblems
✅ **Maps and Documents** - On tables in meeting scenes
✅ **Period Costumes** - Victorian, modern suits, uniforms

---

## Image-Script Matching Logic

```python
# Auto-select mood based on script section
if "collapse" or "crisis" or "death" → dark_moody
if "1970" or "century" or "empire" → historical  
if "war" or "invasion" or "military" → action_dramatic
if "café" or "paris" or "france" → warm_nostalgic
else → bright_sunny

# Auto-select scene type  
if "street" or "city" → street_wide
if "he" or "she" or "man" or "woman" → character_focus
if "meeting" or "discuss" or "table" → meeting_room
if "mountain" or "ocean" or "geography" → landscape_vista
if "build" or "factory" or "mine" → construction_work
```

---

## Example Prompts

### Ghibli + Bright Sunny + Street Wide:
```
Studio Ghibli style illustration, animated cartoon, wide establishing shot 
of a European city street with colorful buildings on both sides, people 
walking, vintage cars, bright sunny day, vibrant colors, clear blue sky 
with fluffy white clouds, cheerful atmosphere, clean linework, expressive 
characters, detailed illustrated backgrounds
```

### Impressionist + Somber + Character Focus:
```
Impressionist oil painting style, like Renoir, medium shot focused on 
workers carrying heavy bags, tired expressions, muted gray-blue color 
palette, overcast lighting, visible brushstrokes, classic oil painting 
technique, traditional art gallery quality
```

### Ghibli + Dark Moody + Character Focus:
```
Studio Ghibli style illustration, animated cartoon, close up of a worried 
businessman in a suit sitting alone on a bench, city skyline visible 
through window, dark twilight atmosphere, moody lighting, melancholic mood, 
clean linework, expressive character
```
