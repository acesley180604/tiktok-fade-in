# TikTok Fade-In Hook Video Generator

Create TikTok-style hook videos with sprite animations and fade-in effects.

## Features

- 9:16 vertical format (1080x1920) optimized for TikTok/Reels
- Full-width text overlay at top (TikTok native style)
- Sprite animation with customizable fade-in timing
- TikTok Sans font support

## Video Structure

| Time | Effect |
|------|--------|
| 0-2s | Black screen + text overlay at top |
| 2-5s | Sprite fades in at center (3-second fade) |

## Requirements

- Python 3.10+
- Pillow
- MoviePy
- TikTok Sans font (place in `~/Downloads/TikTok_Sans/`)

## Installation

```bash
pip install pillow moviepy
```

## Usage

```bash
python tiktok_ad_builder.py <sprite_sheet.png> [output.mp4]
```

### Example

```bash
python tiktok_ad_builder.py ~/sprites/cat.png ~/Downloads/hook_video.mp4
```

## Customization

Edit `tiktok_ad_builder.py` to customize:
- `hook_text` - The text displayed at the top
- `black_duration` - How long before sprite appears (default: 2s)
- `fade_duration` - How long the fade-in takes (default: 3s)
- `sprite_scale` - Size of the sprite (default: 14x)
