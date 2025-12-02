from PIL import Image, ImageDraw, ImageFont
import numpy as np
from moviepy import ImageSequenceClip
from moviepy.video.fx import FadeIn

# TikTok Sans fonts
TIKTOK_FONT_BOLD = "/Users/acesley/Downloads/TikTok_Sans/static/TikTokSans-Bold.ttf"
TIKTOK_FONT_SEMIBOLD = "/Users/acesley/Downloads/TikTok_Sans/static/TikTokSans-SemiBold.ttf"
TIKTOK_FONT_MEDIUM = "/Users/acesley/Downloads/TikTok_Sans/static/TikTokSans-Medium.ttf"

# Video dimensions (9:16 TikTok)
VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1920


def get_font(size, weight="bold"):
    fonts = {
        "bold": TIKTOK_FONT_BOLD,
        "semibold": TIKTOK_FONT_SEMIBOLD,
        "medium": TIKTOK_FONT_MEDIUM
    }
    try:
        return ImageFont.truetype(fonts.get(weight, TIKTOK_FONT_BOLD), size)
    except:
        return ImageFont.load_default()


def wrap_text(text, font, max_width):
    """Word wrap text to fit within max_width"""
    words = text.split()
    lines = []
    current_line = []

    temp_img = Image.new("RGBA", (1, 1))
    temp_draw = ImageDraw.Draw(temp_img)

    for word in words:
        test_line = ' '.join(current_line + [word])
        bbox = temp_draw.textbbox((0, 0), test_line, font=font)
        if bbox[2] - bbox[0] <= max_width:
            current_line.append(word)
        else:
            if current_line:
                lines.append(' '.join(current_line))
            current_line = [word]
    if current_line:
        lines.append(' '.join(current_line))

    return lines


def create_text_box(text, font_size=48, max_width=900, bg_color=(255, 255, 255, 245),
                    text_color=(0, 0, 0), padding=30, radius=16, shadow=False):
    """Create TikTok-style text box with white bg and black text"""
    font = get_font(font_size, "bold")
    lines = wrap_text(text, font, max_width - padding * 2)

    line_height = font_size + 14
    box_height = len(lines) * line_height + padding * 2
    box_width = max_width

    # Create with transparency
    text_img = Image.new("RGBA", (box_width, box_height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(text_img)

    # Draw rounded rectangle background
    if bg_color[3] > 0:  # If background is visible
        draw.rounded_rectangle(
            [(0, 0), (box_width - 1, box_height - 1)],
            radius=radius,
            fill=bg_color
        )

    # Draw shadow if requested (for floating text)
    if shadow and bg_color[3] == 0:
        # Draw text shadow
        for line_idx, line in enumerate(lines):
            bbox = draw.textbbox((0, 0), line, font=font)
            text_width = bbox[2] - bbox[0]
            x = (box_width - text_width) // 2
            y = padding + line_idx * line_height
            # Shadow
            draw.text((x + 3, y + 3), line, fill=(0, 0, 0, 180), font=font)

    # Draw text centered
    for line_idx, line in enumerate(lines):
        bbox = draw.textbbox((0, 0), line, font=font)
        text_width = bbox[2] - bbox[0]
        x = (box_width - text_width) // 2
        y = padding + line_idx * line_height
        draw.text((x, y), line, fill=text_color, font=font)

    return text_img


def extract_sprites(sprite_sheet_path, grid_w=32, grid_h=38):
    """Extract animation frames from sprite sheet"""
    sheet = Image.open(sprite_sheet_path).convert("RGBA")
    sprites = []
    sheet_w, sheet_h = sheet.size

    def is_empty(img, x, y, w, h):
        region = img.crop((x, y, x+w, y+h))
        pixels = list(region.getdata())
        non_empty = sum(1 for p in pixels if len(p) > 3 and p[3] > 10)
        return non_empty < (w * h * 0.05)

    for row in range(sheet_h // grid_h + 1):
        for col in range(sheet_w // grid_w + 1):
            x, y = col * grid_w, row * grid_h
            if x + grid_w > sheet_w or y + grid_h > sheet_h:
                continue
            if not is_empty(sheet, x, y, grid_w, grid_h):
                sprites.append(sheet.crop((x, y, x + grid_w, y + grid_h)))

    return sprites


def build_phase1_frame(frame_idx, sprites, fps=24):
    """
    Phase 1: The Hook (0:00 - 0:05)
    - 0-2s: Black screen with text at top
    - 2-5s: Sprite fades in at CENTER of screen (3s fade)
    """
    frame = Image.new("RGBA", (VIDEO_WIDTH, VIDEO_HEIGHT), (12, 12, 15, 255))

    # Hook text
    hook_text = "When she's so beautiful that it makes you wanna start focusing on your career, hit the gym, be a kind human and become a billionaire."

    # Measure text first to calculate compact box height
    font = get_font(44, "bold")
    lines = wrap_text(hook_text, font, VIDEO_WIDTH - 100)  # 50px margin each side

    line_height = 54
    top_padding = int(VIDEO_HEIGHT * 0.12)  # ~15% from top (below TikTok header)
    text_padding = 30  # Padding around text inside white box
    total_text_height = len(lines) * line_height

    # White box height = just enough to fit text + padding
    white_box_height = top_padding + total_text_height + text_padding * 2

    # Create FULL WIDTH white background (compact)
    white_box = Image.new("RGBA", (VIDEO_WIDTH, white_box_height), (255, 255, 255, 255))
    draw = ImageDraw.Draw(white_box)

    # Draw text - starts at top_padding (below TikTok header area)
    start_y = top_padding + text_padding

    for line_idx, line in enumerate(lines):
        bbox = draw.textbbox((0, 0), line, font=font)
        text_width = bbox[2] - bbox[0]
        x = (VIDEO_WIDTH - text_width) // 2
        y = start_y + line_idx * line_height
        draw.text((x, y), line, fill=(0, 0, 0, 255), font=font)

    # Paste white box at top
    frame.paste(white_box, (0, 0), white_box)

    # Calculate timing
    current_time = frame_idx / fps
    black_duration = 2.0  # First 2 seconds = black (no sprite)
    fade_duration = 3.0   # Last 3 seconds = sprite fades in

    # Sprite animation - CENTERED in middle of screen
    sprite_scale = 14
    sprite_w = 32 * sprite_scale
    sprite_h = 38 * sprite_scale

    idle_sprites = sprites[:12] if len(sprites) >= 12 else sprites
    sprite_idx = (frame_idx // 4) % len(idle_sprites)
    sprite = idle_sprites[sprite_idx].resize((sprite_w, sprite_h), Image.NEAREST)

    # Center sprite in MIDDLE of screen (below white box area)
    sprite_x = (VIDEO_WIDTH - sprite_w) // 2
    sprite_y = (VIDEO_HEIGHT - sprite_h) // 2 + 100  # Centered, slightly below middle

    # Only show sprite after 2 seconds, with fade in
    if current_time >= black_duration:
        # Calculate fade opacity (0 to 255 over 3 seconds)
        fade_progress = (current_time - black_duration) / fade_duration
        fade_progress = min(1.0, fade_progress)  # Clamp to 1.0
        opacity = int(255 * fade_progress)

        # Apply opacity to sprite
        if opacity > 0:
            sprite_with_fade = sprite.copy()
            # Adjust alpha channel
            r, g, b, a = sprite_with_fade.split()
            a = a.point(lambda p: int(p * fade_progress))
            sprite_with_fade = Image.merge("RGBA", (r, g, b, a))
            frame.paste(sprite_with_fade, (sprite_x, sprite_y), sprite_with_fade)

    return frame


def build_phase2_frame(frame_idx, sprites, sub_phase, fps=24):
    """
    Phase 2: The Pivot & Demo (0:06 - 0:10)
    - Instructional text at top 20%
    - Demo text at 30-40%
    - Device/sprite in center-bottom (40-90%)
    """
    frame = Image.new("RGBA", (VIDEO_WIDTH, VIDEO_HEIGHT), (8, 8, 10, 255))

    # Instructional text 1 - floating with shadow (no bg box)
    if sub_phase >= 0:
        text1 = "Get this app called 'Rise' ASAP"
        text_box1 = create_text_box(
            text1,
            font_size=42,
            max_width=900,
            bg_color=(0, 0, 0, 0),  # Transparent bg
            text_color=(255, 255, 255),
            padding=20,
            shadow=True
        )
        text1_x = (VIDEO_WIDTH - text_box1.width) // 2
        text1_y = int(VIDEO_HEIGHT * 0.15)
        frame.paste(text_box1, (text1_x, text1_y), text_box1)

    # Instructional text 2 - demo description
    if sub_phase >= 1:
        text2 = "Generate a personalised 66 days life reset program"
        text_box2 = create_text_box(
            text2,
            font_size=38,
            max_width=int(VIDEO_WIDTH * 0.85),
            bg_color=(0, 0, 0, 0),
            text_color=(255, 255, 255),
            padding=15,
            shadow=True
        )
        text2_x = (VIDEO_WIDTH - text_box2.width) // 2
        text2_y = int(VIDEO_HEIGHT * 0.28)
        frame.paste(text_box2, (text2_x, text2_y), text_box2)

    # Sprite as "device" - center-bottom (simulating app demo)
    sprite_scale = 12
    sprite_w = 32 * sprite_scale
    sprite_h = 38 * sprite_scale

    # Use different animation frames for "activity"
    active_sprites = sprites[24:36] if len(sprites) >= 36 else sprites[:12]
    sprite_idx = (frame_idx // 3) % len(active_sprites)
    sprite = active_sprites[sprite_idx].resize((sprite_w, sprite_h), Image.NEAREST)

    sprite_x = (VIDEO_WIDTH - sprite_w) // 2
    sprite_y = int(VIDEO_HEIGHT * 0.50)

    frame.paste(sprite, (sprite_x, sprite_y), sprite)

    return frame


def build_phase3_frame(frame_idx, sprites, fps=24):
    """
    Phase 3: The CTA & Payoff (0:11 - 0:12)
    - CTA text DEAD CENTER (50-60% Y)
    - Large/Bold, unmissable
    - Sprite/widget in background
    """
    frame = Image.new("RGBA", (VIDEO_WIDTH, VIDEO_HEIGHT), (10, 10, 12, 255))

    # Background sprite (subtle)
    sprite_scale = 10
    sprite_w = 32 * sprite_scale
    sprite_h = 38 * sprite_scale

    idle_sprites = sprites[:8] if len(sprites) >= 8 else sprites
    sprite_idx = (frame_idx // 5) % len(idle_sprites)
    sprite = idle_sprites[sprite_idx].resize((sprite_w, sprite_h), Image.NEAREST)

    # Position sprite slightly faded in background
    sprite_x = (VIDEO_WIDTH - sprite_w) // 2
    sprite_y = int(VIDEO_HEIGHT * 0.25)

    # Make sprite semi-transparent for background
    sprite_faded = sprite.copy()
    alpha = sprite_faded.split()[3]
    alpha = alpha.point(lambda p: int(p * 0.4))
    sprite_faded.putalpha(alpha)

    frame.paste(sprite_faded, (sprite_x, sprite_y), sprite_faded)

    # CTA Text - DEAD CENTER, large and bold
    cta_text = "Comment 'Rise' to get a download link in your DM"

    cta_box = create_text_box(
        cta_text,
        font_size=52,
        max_width=950,
        bg_color=(255, 255, 255, 250),
        text_color=(0, 0, 0),
        padding=40,
        radius=16
    )

    cta_x = (VIDEO_WIDTH - cta_box.width) // 2
    cta_y = int(VIDEO_HEIGHT * 0.45)  # Dead center

    frame.paste(cta_box, (cta_x, cta_y), cta_box)

    return frame


def create_tiktok_ad(sprite_sheet_path, output_path, fps=24):
    """
    Create TikTok-style Hook video

    Timeline:
    - Phase 1: 0:00 - 0:05 (Hook) - 5 seconds with 3s fade-in
    """

    print("Loading sprites...")
    sprites = extract_sprites(sprite_sheet_path)
    print(f"Extracted {len(sprites)} sprite frames")

    video_frames = []

    # Phase 1: Hook (0-5s) with 3s fade-in
    phase1_duration = 5
    phase1_frames = int(phase1_duration * fps)
    print(f"Building Hook video ({phase1_frames} frames, {phase1_duration}s)")

    for i in range(phase1_frames):
        frame = build_phase1_frame(i, sprites, fps)
        video_frames.append(np.array(frame.convert("RGB")))

    total_frames = len(video_frames)
    total_duration = total_frames / fps
    print(f"\nTotal: {total_frames} frames ({total_duration}s)")

    # Create video clip
    clip = ImageSequenceClip(video_frames, fps=fps)

    # No global fade - sprite fade is handled in frame building

    # Export
    print(f"\nExporting video...")
    clip.write_videofile(
        output_path,
        codec="libx264",
        fps=fps,
        preset="medium",
        bitrate="8000k"
    )

    print(f"\n✓ TikTok Hook saved: {output_path}")
    print(f"  Resolution: {VIDEO_WIDTH}x{VIDEO_HEIGHT} (9:16)")
    print(f"  Duration: {total_duration}s")
    print(f"  Fade-in: 3s")

    return output_path


if __name__ == "__main__":
    import sys

    sprite_path = sys.argv[1] if len(sys.argv) > 1 else None
    output = sys.argv[2] if len(sys.argv) > 2 else "/Users/acesley/Downloads/tiktok_ad.mp4"

    if not sprite_path:
        print("Usage: python tiktok_ad_builder.py <sprite_sheet.png> [output.mp4]")
        sys.exit(1)

    create_tiktok_ad(sprite_path, output)
