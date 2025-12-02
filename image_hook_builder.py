from PIL import Image, ImageDraw, ImageFont
import numpy as np
from moviepy import ImageSequenceClip

# TikTok Sans fonts
TIKTOK_FONT_BOLD = "/Users/acesley/Downloads/TikTok_Sans/static/TikTokSans-Bold.ttf"

# Video dimensions (9:16 TikTok)
VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1920


def get_font(size, weight="bold"):
    try:
        return ImageFont.truetype(TIKTOK_FONT_BOLD, size)
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


def build_frame(frame_idx, image, hook_text, fps=24):
    """
    Build a single frame:
    - 0-2s: Black screen + text overlay at top
    - 2-5s: Image fades in at center (3s fade)
    """
    frame = Image.new("RGBA", (VIDEO_WIDTH, VIDEO_HEIGHT), (12, 12, 15, 255))

    # Measure text first to calculate compact box height
    font = get_font(44)
    lines = wrap_text(hook_text, font, VIDEO_WIDTH - 100)

    line_height = 54
    top_padding = int(VIDEO_HEIGHT * 0.12)  # ~15% from top
    text_padding = 30
    total_text_height = len(lines) * line_height

    # White box height = just enough to fit text + padding
    white_box_height = top_padding + total_text_height + text_padding * 2

    # Create FULL WIDTH white background (compact)
    white_box = Image.new("RGBA", (VIDEO_WIDTH, white_box_height), (255, 255, 255, 255))
    draw = ImageDraw.Draw(white_box)

    # Draw text
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
    black_duration = 2.0  # First 2 seconds = no image
    fade_duration = 3.0   # Last 3 seconds = image fades in

    # Scale image to FULL WIDTH (no horizontal padding)
    img_w, img_h = image.size

    # Scale to full width
    scale = VIDEO_WIDTH / img_w
    new_w = VIDEO_WIDTH
    new_h = int(img_h * scale)

    scaled_image = image.resize((new_w, new_h), Image.LANCZOS)

    # Position: full width, centered vertically in the dark area below white box
    img_x = 0  # Full width - start at edge
    img_y = white_box_height + (VIDEO_HEIGHT - white_box_height - new_h) // 2

    # Only show image after 2 seconds, with fade in
    if current_time >= black_duration:
        fade_progress = (current_time - black_duration) / fade_duration
        fade_progress = min(1.0, fade_progress)

        if fade_progress > 0:
            # Convert to RGBA if needed
            if scaled_image.mode != 'RGBA':
                scaled_image = scaled_image.convert('RGBA')

            # Apply fade
            img_with_fade = scaled_image.copy()
            r, g, b, a = img_with_fade.split()
            a = a.point(lambda p: int(p * fade_progress))
            img_with_fade = Image.merge("RGBA", (r, g, b, a))

            frame.paste(img_with_fade, (img_x, img_y), img_with_fade)

    return frame


def create_image_hook_video(image_path, output_path, hook_text, duration=5, fps=24):
    """
    Create TikTok-style hook video from an image

    Timeline:
    - 0-2s: Black screen + text at top
    - 2-5s: Image fades in at center (3s fade)
    """

    print(f"Loading image: {image_path}")
    image = Image.open(image_path).convert("RGBA")
    print(f"Image size: {image.size}")

    video_frames = []
    total_frames = int(duration * fps)

    print(f"Building {total_frames} frames ({duration}s)")

    for i in range(total_frames):
        frame = build_frame(i, image, hook_text, fps)
        video_frames.append(np.array(frame.convert("RGB")))

    print(f"\nCreating video clip...")
    clip = ImageSequenceClip(video_frames, fps=fps)

    print(f"Exporting video...")
    clip.write_videofile(
        output_path,
        codec="libx264",
        fps=fps,
        preset="medium",
        bitrate="8000k"
    )

    print(f"\n✓ Video saved: {output_path}")
    print(f"  Resolution: {VIDEO_WIDTH}x{VIDEO_HEIGHT} (9:16)")
    print(f"  Duration: {duration}s")
    print(f"  Timeline: 2s black + 3s fade-in")

    return output_path


if __name__ == "__main__":
    import sys

    image_path = sys.argv[1] if len(sys.argv) > 1 else None
    output = sys.argv[2] if len(sys.argv) > 2 else "/Users/acesley/Downloads/hook_video.mp4"

    if not image_path:
        print("Usage: python image_hook_builder.py <image.jpg> [output.mp4]")
        sys.exit(1)

    # Default hook text - can be customized
    hook_text = "When the ADHD meds help you remember to do stuff but you forget to take the meds..."

    create_image_hook_video(image_path, output, hook_text)
