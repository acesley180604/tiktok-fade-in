"""
TikTok Hook Video Generator - Web App

Upload an image, generate hooks with AI (OpenRouter), and create TikTok-style videos.
"""

import os
import uuid
import tempfile
import time
from pathlib import Path
from flask import Flask, request, jsonify, send_file, render_template_string
from werkzeug.utils import secure_filename
from PIL import Image, ImageDraw, ImageFont
import numpy as np
from moviepy import ImageSequenceClip
import requests

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload
app.config['UPLOAD_FOLDER'] = tempfile.mkdtemp()

# OpenRouter Configuration
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")

# Apify Configuration (for Reddit scraping)
APIFY_API_TOKEN = os.getenv("APIFY_API_TOKEN", "")
APIFY_REDDIT_ACTOR = "trudax~reddit-scraper-lite"  # Free/cheap Reddit scraper

# TikTok Sans font - try multiple paths for local and production
FONT_PATHS = [
    os.path.expanduser("~/Downloads/TikTok_Sans/static/TikTokSans-Bold.ttf"),  # Local macOS
    "/app/fonts/TikTokSans-Bold.ttf",  # Docker with bundled font
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",  # Fallback on Linux
]

def find_font():
    for path in FONT_PATHS:
        if os.path.exists(path):
            return path
    return None

TIKTOK_FONT_BOLD = find_font()

# Video dimensions (9:16 TikTok)
VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1920

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def get_font(size):
    if TIKTOK_FONT_BOLD:
        try:
            return ImageFont.truetype(TIKTOK_FONT_BOLD, size)
        except Exception:
            pass
    # Fallback to default font
    return ImageFont.load_default()


def wrap_text(text, font, max_width):
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


def generate_hooks_with_llm(image_description, num_hooks=5):
    """Generate hook texts using OpenRouter API"""
    if not OPENROUTER_API_KEY:
        return ["Add your hook text here..."]

    prompt = f"""You are a viral TikTok content creator. Based on this image description, generate {num_hooks} different hook texts for a TikTok video.

Image: {image_description}

Requirements:
- Each hook should be 1-2 sentences max
- Use relatable, emotional triggers
- Start with "When..." or similar engaging openers
- Make it feel like a peer recommendation, not an ad
- Target the "grindset" or relatable content demographic

Return ONLY the hooks, one per line, no numbering or extra text."""

    try:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "meta-llama/llama-3.1-8b-instruct:free",
                "messages": [{"role": "user", "content": prompt}]
            },
            timeout=30
        )
        response.raise_for_status()

        content = response.json()["choices"][0]["message"]["content"]
        hooks = [h.strip() for h in content.strip().split("\n") if h.strip()]
        return hooks[:num_hooks]
    except Exception as e:
        print(f"LLM Error: {e}")
        return ["When this hits different...", "POV: You finally get it...", "This is your sign..."]


def describe_image_with_llm(image_path):
    """Get image description using OpenRouter vision model"""
    if not OPENROUTER_API_KEY:
        return "an interesting meme or image"

    import base64

    try:
        with open(image_path, "rb") as f:
            image_data = base64.b64encode(f.read()).decode("utf-8")

        # Determine mime type
        ext = image_path.split(".")[-1].lower()
        mime_type = f"image/{ext}" if ext != "jpg" else "image/jpeg"

        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "meta-llama/llama-3.2-11b-vision-instruct:free",
                "messages": [{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Describe this image in 1-2 sentences. Focus on what's happening, the mood, and any text visible."},
                        {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{image_data}"}}
                    ]
                }]
            },
            timeout=30
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"Vision Error: {e}")
        return "an interesting meme or image"


def fetch_reddit_posts(subreddit_name="adhdmeme", sort="hot", limit=10):
    """Fetch image posts from a subreddit using Apify"""
    if not APIFY_API_TOKEN:
        return {"error": "Apify API not configured. Set APIFY_API_TOKEN in .env"}

    try:
        # Use synchronous API call that waits for completion
        run_url = f"https://api.apify.com/v2/acts/{APIFY_REDDIT_ACTOR}/runs?waitForFinish=120"

        # Map sort to Apify input format
        sort_mapping = {"hot": "hot", "top": "top", "new": "new"}
        apify_sort = sort_mapping.get(sort, "hot")

        payload = {
            "startUrls": [{"url": f"https://www.reddit.com/r/{subreddit_name}/{apify_sort}/"}],
            "maxItems": limit * 3  # Get extra to filter for images
        }

        headers = {
            "Authorization": f"Bearer {APIFY_API_TOKEN}",
            "Content-Type": "application/json"
        }

        # Start the run and wait
        print(f"Starting Apify run for r/{subreddit_name}/{apify_sort}...")
        response = requests.post(run_url, json=payload, headers=headers, timeout=180)
        response.raise_for_status()
        run_data = response.json()

        status = run_data["data"]["status"]
        if status != "SUCCEEDED":
            return {"error": f"Apify run failed with status: {status}"}

        # Get results from dataset
        dataset_id = run_data["data"]["defaultDatasetId"]
        dataset_url = f"https://api.apify.com/v2/datasets/{dataset_id}/items"

        dataset_response = requests.get(dataset_url, headers=headers, timeout=30)
        dataset_response.raise_for_status()
        items = dataset_response.json()

        # Separate posts and comments
        posts = {}
        comments_by_post = {}

        for item in items:
            data_type = item.get("dataType", "")

            if data_type == "post":
                post_id = item.get("id", "")
                # Check if it has images
                image_urls = item.get("imageUrls", [])
                link = item.get("link", "")

                # Try to get image URL
                image_url = None
                if image_urls:
                    image_url = image_urls[0]
                elif link and ("i.redd.it" in link or link.endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp'))):
                    image_url = link

                if image_url:
                    posts[post_id] = {
                        "id": item.get("parsedId", post_id),
                        "title": item.get("title", ""),
                        "image_url": image_url,
                        "score": item.get("upVotes", 0),
                        "permalink": item.get("url", f"https://reddit.com/r/{subreddit_name}"),
                        "top_comments": []
                    }
                    comments_by_post[post_id] = []

            elif data_type == "comment":
                post_id = item.get("postId", "")
                if post_id not in comments_by_post:
                    comments_by_post[post_id] = []

                body = item.get("body", "")
                if body and 10 < len(body) < 300:
                    comments_by_post[post_id].append({
                        "text": body,
                        "score": item.get("upVotes", 0)
                    })

        # Match comments to posts
        for post_id, post in posts.items():
            if post_id in comments_by_post:
                # Sort by score and take top 3
                sorted_comments = sorted(comments_by_post[post_id], key=lambda x: x["score"], reverse=True)
                post["top_comments"] = sorted_comments[:3]

        # Convert to list and limit
        results = list(posts.values())[:limit]

        print(f"Found {len(results)} image posts with comments")
        return {"posts": results}

    except requests.exceptions.RequestException as e:
        print(f"Apify API error: {e}")
        return {"error": f"Apify API error: {str(e)}"}
    except Exception as e:
        print(f"Error fetching posts: {e}")
        import traceback
        traceback.print_exc()
        return {"error": f"Error fetching posts: {str(e)}"}


def rephrase_comment_as_hook(comment_text, post_title):
    """Use LLM to rephrase a Reddit comment into a TikTok hook using copywriting frameworks"""
    if not OPENROUTER_API_KEY:
        return comment_text

    prompt = f"""Transform this Reddit comment into a viral TikTok hook using proven copywriting frameworks.

Post title: {post_title}
Comment: {comment_text}

Choose ONE of these frameworks that best fits the content:

1. **PAS (Problem, Agitate, Solution)** - Start with a relatable problem, make it feel urgent, offer hope
   Example: "Tired of [problem]? → It's affecting your [life area] → Here's how to fix it"

2. **AIDA (Attention, Interest, Desire, Action)** - Grab attention, build interest, create desire
   Example: "Sick of [problem]? → Imagine [better state] → Experience [benefit] → Start now"

3. **BAB (Before, After, Bridge)** - Show transformation
   Example: "[Bad state before] → [Good state after] → [How to get there]"

4. **Fear/Pain Hook** - Address fears or pain points directly
   Example: "Warning: Are you making this mistake?" or "Stop doing [common mistake]"

5. **Social Proof Hook** - Use numbers or testimonials
   Example: "Why [X] people swear by this" or "The method that changed everything"

6. **How-To Hook** - Promise a solution
   Example: "How to [achieve result] without [common obstacle]"

7. **Bizarre/Curiosity Hook** - Create intrigue
   Example: "Why [unexpected thing] is actually [surprising insight]"

RULES:
- Hook must be MAX 50 characters (this is critical!)
- Use emotional triggers that resonate with ADHD community
- Call out the audience directly (e.g., "ADHD brain?", "Fellow ADHDers")
- Make it feel like a friend talking, not an ad
- Focus on BENEFITS not features
- Use relatable language (casual, authentic)
- Remove all Reddit-specific references

Return ONLY the hook text (max 50 chars), nothing else."""

    try:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "meta-llama/llama-3.1-8b-instruct:free",
                "messages": [{"role": "user", "content": prompt}]
            },
            timeout=30
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print(f"Rephrase Error: {e}")
        return comment_text


def download_reddit_image(image_url):
    """Download image from URL and save to temp folder"""
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        response = requests.get(image_url, headers=headers, timeout=30)
        response.raise_for_status()

        # Determine extension
        content_type = response.headers.get('content-type', '')
        if 'png' in content_type:
            ext = 'png'
        elif 'gif' in content_type:
            ext = 'gif'
        elif 'webp' in content_type:
            ext = 'webp'
        else:
            ext = 'jpg'

        filename = f"{uuid.uuid4()}.{ext}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)

        with open(filepath, 'wb') as f:
            f.write(response.content)

        return filepath
    except Exception as e:
        print(f"Download Error: {e}")
        return None


def build_frame(frame_idx, image, hook_text, fps=24):
    """Build a single video frame"""
    frame = Image.new("RGBA", (VIDEO_WIDTH, VIDEO_HEIGHT), (12, 12, 15, 255))

    font = get_font(44)
    lines = wrap_text(hook_text, font, VIDEO_WIDTH - 100)

    line_height = 54
    top_padding = int(VIDEO_HEIGHT * 0.12)
    text_padding = 30
    total_text_height = len(lines) * line_height
    white_box_height = top_padding + total_text_height + text_padding * 2

    white_box = Image.new("RGBA", (VIDEO_WIDTH, white_box_height), (255, 255, 255, 255))
    draw = ImageDraw.Draw(white_box)

    start_y = top_padding + text_padding
    for line_idx, line in enumerate(lines):
        bbox = draw.textbbox((0, 0), line, font=font)
        text_width = bbox[2] - bbox[0]
        x = (VIDEO_WIDTH - text_width) // 2
        y = start_y + line_idx * line_height
        draw.text((x, y), line, fill=(0, 0, 0, 255), font=font)

    frame.paste(white_box, (0, 0), white_box)

    current_time = frame_idx / fps
    black_duration = 2.0
    fade_duration = 3.0

    img_w, img_h = image.size
    scale = VIDEO_WIDTH / img_w
    new_w = VIDEO_WIDTH
    new_h = int(img_h * scale)

    scaled_image = image.resize((new_w, new_h), Image.LANCZOS)

    img_x = 0
    img_y = white_box_height + (VIDEO_HEIGHT - white_box_height - new_h) // 2

    if current_time >= black_duration:
        fade_progress = min(1.0, (current_time - black_duration) / fade_duration)

        if fade_progress > 0:
            if scaled_image.mode != 'RGBA':
                scaled_image = scaled_image.convert('RGBA')

            img_with_fade = scaled_image.copy()
            r, g, b, a = img_with_fade.split()
            a = a.point(lambda p: int(p * fade_progress))
            img_with_fade = Image.merge("RGBA", (r, g, b, a))

            frame.paste(img_with_fade, (img_x, img_y), img_with_fade)

    return frame


def create_video(image_path, hook_text, output_path, duration=5, fps=24):
    """Create TikTok hook video"""
    image = Image.open(image_path).convert("RGBA")

    video_frames = []
    total_frames = int(duration * fps)

    for i in range(total_frames):
        frame = build_frame(i, image, hook_text, fps)
        video_frames.append(np.array(frame.convert("RGB")))

    clip = ImageSequenceClip(video_frames, fps=fps)
    clip.write_videofile(
        output_path,
        codec="libx264",
        fps=fps,
        preset="medium",
        bitrate="8000k"
    )

    return output_path


# HTML Template - Multi-file upload with batch processing
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Hook Video Generator</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }

        :root {
            --bg: #09090b;
            --surface: #18181b;
            --surface-2: #27272a;
            --border: #27272a;
            --border-hover: #3f3f46;
            --text: #fafafa;
            --text-secondary: #a1a1aa;
            --text-muted: #71717a;
            --success: #22c55e;
            --error: #ef4444;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Inter', system-ui, sans-serif;
            background: var(--bg);
            color: var(--text);
            min-height: 100vh;
        }

        .app {
            max-width: 720px;
            margin: 0 auto;
            padding: 24px 16px;
            min-height: 100vh;
            display: flex;
            flex-direction: column;
        }

        /* Header */
        .header {
            padding: 16px 0 24px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .header-left h1 {
            font-size: 1.25rem;
            font-weight: 600;
            letter-spacing: -0.025em;
        }

        .header-left p {
            color: var(--text-muted);
            font-size: 0.8125rem;
            margin-top: 2px;
        }

        .header-right {
            display: flex;
            gap: 8px;
        }

        /* Upload section */
        .upload-area {
            border: 1px dashed var(--border);
            border-radius: 12px;
            padding: 32px 20px;
            text-align: center;
            cursor: pointer;
            transition: all 0.2s ease;
            background: var(--surface);
            margin-bottom: 20px;
        }

        .upload-area:hover {
            border-color: var(--border-hover);
            background: var(--surface-2);
        }

        .upload-area.dragover {
            border-color: var(--text);
            border-style: solid;
        }

        .upload-area .icon {
            width: 36px;
            height: 36px;
            margin: 0 auto 10px;
            opacity: 0.5;
        }

        .upload-area h3 {
            font-size: 0.875rem;
            font-weight: 500;
            margin-bottom: 4px;
        }

        .upload-area p {
            color: var(--text-muted);
            font-size: 0.75rem;
        }

        /* Items list */
        .items-list {
            display: flex;
            flex-direction: column;
            gap: 12px;
            flex: 1;
            overflow-y: auto;
            padding-bottom: 100px;
        }

        .item-card {
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 10px;
            padding: 14px;
            display: flex;
            gap: 14px;
            animation: slideIn 0.2s ease;
        }

        @keyframes slideIn {
            from { opacity: 0; transform: translateY(8px); }
            to { opacity: 1; transform: translateY(0); }
        }

        .item-card.processing {
            opacity: 0.7;
        }

        .item-card.completed {
            border-color: var(--success);
        }

        .item-card.error {
            border-color: var(--error);
        }

        .item-thumbnail {
            width: 80px;
            height: 80px;
            border-radius: 6px;
            object-fit: cover;
            background: var(--surface-2);
            flex-shrink: 0;
        }

        .item-content {
            flex: 1;
            min-width: 0;
            display: flex;
            flex-direction: column;
            gap: 8px;
        }

        .item-header {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            gap: 8px;
        }

        .item-name {
            font-size: 0.8125rem;
            font-weight: 500;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }

        .item-status {
            font-size: 0.6875rem;
            padding: 2px 8px;
            border-radius: 10px;
            background: var(--surface-2);
            color: var(--text-muted);
            white-space: nowrap;
        }

        .item-status.ready { background: var(--border); color: var(--text-secondary); }
        .item-status.processing { background: var(--border); color: var(--text); }
        .item-status.completed { background: rgba(34, 197, 94, 0.2); color: var(--success); }
        .item-status.error { background: rgba(239, 68, 68, 0.2); color: var(--error); }

        .item-hook-input {
            width: 100%;
            background: var(--bg);
            border: 1px solid var(--border);
            border-radius: 6px;
            padding: 8px 10px;
            color: var(--text);
            font-size: 0.8125rem;
            font-family: inherit;
            resize: none;
            min-height: 52px;
            line-height: 1.4;
        }

        .item-hook-input:focus {
            outline: none;
            border-color: var(--border-hover);
        }

        .item-hook-input::placeholder {
            color: var(--text-muted);
        }

        .item-hook-input:disabled {
            opacity: 0.5;
            cursor: not-allowed;
        }

        .item-actions {
            display: flex;
            gap: 8px;
            margin-top: auto;
        }

        .item-btn {
            padding: 6px 12px;
            border-radius: 6px;
            font-size: 0.75rem;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.15s ease;
            text-decoration: none;
            display: inline-flex;
            align-items: center;
            gap: 4px;
        }

        .item-btn-download {
            background: var(--text);
            color: var(--bg);
            border: none;
        }

        .item-btn-remove {
            background: transparent;
            color: var(--text-muted);
            border: 1px solid var(--border);
        }

        .item-btn-remove:hover {
            border-color: var(--error);
            color: var(--error);
        }

        /* Footer / Actions */
        .footer {
            position: fixed;
            bottom: 0;
            left: 0;
            right: 0;
            background: linear-gradient(transparent, var(--bg) 20%);
            padding: 20px 16px 24px;
        }

        .footer-content {
            max-width: 720px;
            margin: 0 auto;
            display: flex;
            gap: 10px;
        }

        .btn {
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
            padding: 12px 20px;
            border-radius: 8px;
            font-size: 0.875rem;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.15s ease;
            text-decoration: none;
            flex: 1;
        }

        .btn-primary {
            background: var(--text);
            color: var(--bg);
            border: none;
        }

        .btn-primary:hover {
            opacity: 0.9;
        }

        .btn-primary:disabled {
            opacity: 0.25;
            cursor: not-allowed;
        }

        .btn-secondary {
            background: transparent;
            color: var(--text);
            border: 1px solid var(--border);
        }

        .btn-secondary:hover {
            background: var(--surface);
        }

        /* Empty state */
        .empty-state {
            text-align: center;
            padding: 40px 20px;
            color: var(--text-muted);
        }

        .empty-state p {
            font-size: 0.875rem;
        }

        /* Progress bar */
        .progress-bar {
            height: 3px;
            background: var(--border);
            border-radius: 2px;
            overflow: hidden;
            margin-top: 8px;
        }

        .progress-fill {
            height: 100%;
            background: var(--text);
            transition: width 0.3s ease;
        }

        /* Count badge */
        .count-badge {
            background: var(--surface-2);
            color: var(--text-secondary);
            font-size: 0.75rem;
            padding: 4px 10px;
            border-radius: 12px;
        }

        input[type="file"] { display: none; }

        .hidden { display: none !important; }

        /* Tabs */
        .tabs {
            display: flex;
            gap: 4px;
            background: var(--surface);
            padding: 4px;
            border-radius: 10px;
            margin-bottom: 20px;
        }

        .tab {
            flex: 1;
            padding: 10px 16px;
            border: none;
            background: transparent;
            color: var(--text-muted);
            font-size: 0.875rem;
            font-weight: 500;
            cursor: pointer;
            border-radius: 6px;
            transition: all 0.15s ease;
        }

        .tab:hover {
            color: var(--text-secondary);
        }

        .tab.active {
            background: var(--surface-2);
            color: var(--text);
        }

        .tab-content {
            display: none;
        }

        .tab-content.active {
            display: block;
        }

        /* Reddit posts */
        .reddit-controls {
            display: flex;
            gap: 10px;
            margin-bottom: 16px;
        }

        .reddit-controls select {
            flex: 1;
            padding: 10px 12px;
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 8px;
            color: var(--text);
            font-size: 0.875rem;
        }

        .reddit-post {
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 10px;
            padding: 14px;
            margin-bottom: 12px;
            animation: slideIn 0.2s ease;
        }

        .reddit-post-header {
            display: flex;
            gap: 12px;
            margin-bottom: 12px;
        }

        .reddit-post-image {
            width: 120px;
            height: 120px;
            border-radius: 8px;
            object-fit: cover;
            background: var(--surface-2);
            cursor: pointer;
        }

        .reddit-post-info {
            flex: 1;
        }

        .reddit-post-title {
            font-size: 0.875rem;
            font-weight: 500;
            margin-bottom: 6px;
            line-height: 1.4;
        }

        .reddit-post-meta {
            font-size: 0.75rem;
            color: var(--text-muted);
            margin-bottom: 8px;
        }

        .reddit-post-link {
            font-size: 0.75rem;
            color: var(--text-secondary);
            text-decoration: none;
        }

        .reddit-post-link:hover {
            text-decoration: underline;
        }

        .reddit-comments {
            margin-top: 12px;
            padding-top: 12px;
            border-top: 1px solid var(--border);
        }

        .reddit-comments-title {
            font-size: 0.75rem;
            color: var(--text-muted);
            margin-bottom: 8px;
        }

        .reddit-comment {
            background: var(--bg);
            padding: 10px 12px;
            border-radius: 6px;
            margin-bottom: 8px;
            cursor: pointer;
            transition: all 0.15s ease;
            border: 1px solid transparent;
        }

        .reddit-comment:hover {
            border-color: var(--border-hover);
        }

        .reddit-comment.selected {
            border-color: var(--text);
        }

        .reddit-comment-text {
            font-size: 0.8125rem;
            line-height: 1.4;
            margin-bottom: 4px;
        }

        .reddit-comment-score {
            font-size: 0.6875rem;
            color: var(--text-muted);
        }

        .reddit-post-actions {
            display: flex;
            gap: 8px;
            margin-top: 12px;
        }

        .reddit-hook-input {
            width: 100%;
            background: var(--bg);
            border: 1px solid var(--border);
            border-radius: 6px;
            padding: 10px 12px;
            color: var(--text);
            font-size: 0.8125rem;
            font-family: inherit;
            resize: none;
            min-height: 60px;
            margin-top: 12px;
        }

        .loading-spinner {
            display: inline-block;
            width: 16px;
            height: 16px;
            border: 2px solid var(--border);
            border-top-color: var(--text);
            border-radius: 50%;
            animation: spin 0.8s linear infinite;
        }

        @keyframes spin {
            to { transform: rotate(360deg); }
        }

        .reddit-loading, .reddit-error {
            text-align: center;
            padding: 40px 20px;
            color: var(--text-muted);
        }

        .reddit-error {
            color: var(--error);
        }
    </style>
</head>
<body>
    <div class="app">
        <div class="header">
            <div class="header-left">
                <h1>Hook Video Generator</h1>
                <p>Create TikTok-style videos</p>
            </div>
            <div class="header-right">
                <span class="count-badge" id="countBadge">0 items</span>
            </div>
        </div>

        <div class="tabs">
            <button class="tab active" data-tab="upload">Upload</button>
            <button class="tab" data-tab="reddit">Reddit</button>
        </div>

        <!-- Upload Tab -->
        <div class="tab-content active" id="uploadTab">
            <div class="upload-area" id="uploadArea">
            <svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                <path d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"/>
            </svg>
            <h3>Upload images</h3>
            <p>Drop multiple files or click to browse</p>
            <input type="file" id="fileInput" accept="image/*" multiple>
        </div>

        <div class="items-list" id="itemsList">
            <div class="empty-state" id="emptyState">
                <p>No images uploaded yet</p>
            </div>
        </div>

        <div class="footer" id="uploadFooter">
            <div class="footer-content">
                <button class="btn btn-secondary" id="addMoreBtn">Add more</button>
                <button class="btn btn-primary" id="generateAllBtn" disabled>Generate all videos</button>
            </div>
        </div>
        </div>

        <!-- Reddit Tab -->
        <div class="tab-content" id="redditTab">
            <div class="reddit-controls">
                <select id="redditSort">
                    <option value="hot">Hot</option>
                    <option value="top">Top (Week)</option>
                    <option value="new">New</option>
                </select>
                <button class="btn btn-secondary" id="refreshReddit">Refresh</button>
            </div>
            <div id="redditPosts">
                <div class="reddit-loading">
                    <div class="loading-spinner"></div>
                    <p style="margin-top: 12px;">Loading posts from r/adhdmeme...</p>
                </div>
            </div>
        </div>
    </div>

    <script>
        const uploadArea = document.getElementById('uploadArea');
        const fileInput = document.getElementById('fileInput');
        const itemsList = document.getElementById('itemsList');
        const emptyState = document.getElementById('emptyState');
        const generateAllBtn = document.getElementById('generateAllBtn');
        const addMoreBtn = document.getElementById('addMoreBtn');
        const countBadge = document.getElementById('countBadge');

        let items = [];
        let itemIdCounter = 0;

        function updateUI() {
            const pendingCount = items.filter(i => i.status === 'pending' || i.status === 'ready').length;
            const totalCount = items.length;

            countBadge.textContent = `${totalCount} item${totalCount !== 1 ? 's' : ''}`;
            emptyState.classList.toggle('hidden', totalCount > 0);
            generateAllBtn.disabled = !items.some(i => i.status === 'ready' && i.hook.trim());
        }

        function createItemCard(item) {
            const card = document.createElement('div');
            card.className = 'item-card';
            card.id = `item-${item.id}`;
            card.innerHTML = `
                <img class="item-thumbnail" src="${item.previewUrl}" alt="Preview">
                <div class="item-content">
                    <div class="item-header">
                        <span class="item-name">${item.file.name}</span>
                        <span class="item-status ready" id="status-${item.id}">Ready</span>
                    </div>
                    <textarea
                        class="item-hook-input"
                        id="hook-${item.id}"
                        placeholder="Enter hook text for this image..."
                        rows="2"
                    >${item.hook}</textarea>
                    <div class="item-actions" id="actions-${item.id}">
                        <button class="item-btn item-btn-remove" onclick="removeItem(${item.id})">Remove</button>
                    </div>
                </div>
            `;
            return card;
        }

        function addItem(file) {
            const id = itemIdCounter++;
            const item = {
                id,
                file,
                previewUrl: URL.createObjectURL(file),
                hook: '',
                status: 'ready',
                videoUrl: null
            };
            items.push(item);

            const card = createItemCard(item);
            itemsList.insertBefore(card, emptyState);

            // Add hook input listener
            const hookInput = document.getElementById(`hook-${id}`);
            hookInput.addEventListener('input', (e) => {
                item.hook = e.target.value;
                updateUI();
            });

            updateUI();
        }

        function removeItem(id) {
            const index = items.findIndex(i => i.id === id);
            if (index > -1) {
                URL.revokeObjectURL(items[index].previewUrl);
                if (items[index].videoUrl) URL.revokeObjectURL(items[index].videoUrl);
                items.splice(index, 1);
            }
            const card = document.getElementById(`item-${id}`);
            if (card) card.remove();
            updateUI();
        }

        function updateItemStatus(id, status, videoUrl = null) {
            const item = items.find(i => i.id === id);
            if (!item) return;

            item.status = status;
            if (videoUrl) item.videoUrl = videoUrl;

            const statusEl = document.getElementById(`status-${id}`);
            const actionsEl = document.getElementById(`actions-${id}`);
            const hookInput = document.getElementById(`hook-${id}`);
            const card = document.getElementById(`item-${id}`);

            statusEl.className = `item-status ${status}`;
            card.className = `item-card ${status}`;

            if (status === 'processing') {
                statusEl.textContent = 'Processing...';
                hookInput.disabled = true;
                actionsEl.innerHTML = '';
            } else if (status === 'completed') {
                statusEl.textContent = 'Completed';
                hookInput.disabled = true;
                actionsEl.innerHTML = `
                    <a class="item-btn item-btn-download" href="${videoUrl}" download="hook_${id}.mp4">Download</a>
                    <button class="item-btn item-btn-remove" onclick="removeItem(${id})">Remove</button>
                `;
            } else if (status === 'error') {
                statusEl.textContent = 'Error';
                hookInput.disabled = false;
                actionsEl.innerHTML = `
                    <button class="item-btn item-btn-remove" onclick="removeItem(${id})">Remove</button>
                `;
            }
        }

        async function processItem(item) {
            updateItemStatus(item.id, 'processing');

            const formData = new FormData();
            formData.append('image', item.file);
            formData.append('hook', item.hook);

            try {
                const response = await fetch('/create-video', {
                    method: 'POST',
                    body: formData
                });

                if (!response.ok) throw new Error('Failed');

                const blob = await response.blob();
                const url = URL.createObjectURL(blob);
                updateItemStatus(item.id, 'completed', url);
            } catch (err) {
                console.error(err);
                updateItemStatus(item.id, 'error');
            }
        }

        async function generateAll() {
            const readyItems = items.filter(i => i.status === 'ready' && i.hook.trim());
            generateAllBtn.disabled = true;
            generateAllBtn.textContent = `Processing 0/${readyItems.length}...`;

            for (let i = 0; i < readyItems.length; i++) {
                generateAllBtn.textContent = `Processing ${i + 1}/${readyItems.length}...`;
                await processItem(readyItems[i]);
            }

            generateAllBtn.textContent = 'Generate all videos';
            updateUI();
        }

        // Event listeners
        uploadArea.addEventListener('dragover', (e) => {
            e.preventDefault();
            uploadArea.classList.add('dragover');
        });

        uploadArea.addEventListener('dragleave', () => {
            uploadArea.classList.remove('dragover');
        });

        uploadArea.addEventListener('drop', (e) => {
            e.preventDefault();
            uploadArea.classList.remove('dragover');
            const files = Array.from(e.dataTransfer.files).filter(f => f.type.startsWith('image/'));
            files.forEach(addItem);
        });

        uploadArea.addEventListener('click', () => fileInput.click());
        addMoreBtn.addEventListener('click', () => fileInput.click());

        fileInput.addEventListener('change', (e) => {
            const files = Array.from(e.target.files).filter(f => f.type.startsWith('image/'));
            files.forEach(addItem);
            fileInput.value = '';
        });

        generateAllBtn.addEventListener('click', generateAll);

        updateUI();

        // ============ Tab Switching ============
        const tabs = document.querySelectorAll('.tab');
        const tabContents = document.querySelectorAll('.tab-content');
        const uploadFooter = document.getElementById('uploadFooter');

        tabs.forEach(tab => {
            tab.addEventListener('click', () => {
                const targetTab = tab.dataset.tab;

                tabs.forEach(t => t.classList.remove('active'));
                tabContents.forEach(c => c.classList.remove('active'));
                tab.classList.add('active');

                if (targetTab === 'upload') {
                    document.getElementById('uploadTab').classList.add('active');
                    uploadFooter.style.display = 'block';
                } else if (targetTab === 'reddit') {
                    document.getElementById('redditTab').classList.add('active');
                    uploadFooter.style.display = 'none';
                    loadRedditPosts();
                }
            });
        });

        // ============ Reddit Functions ============
        const redditPosts = document.getElementById('redditPosts');
        const redditSort = document.getElementById('redditSort');
        const refreshReddit = document.getElementById('refreshReddit');
        let redditLoaded = false;

        async function loadRedditPosts() {
            if (redditLoaded) return;

            const sort = redditSort.value;
            redditPosts.innerHTML = `
                <div class="reddit-loading">
                    <div class="loading-spinner"></div>
                    <p style="margin-top: 12px;">Loading posts from r/adhdmeme...</p>
                </div>
            `;

            try {
                const response = await fetch(`/reddit/posts?sort=${sort}&limit=10`);
                const data = await response.json();

                if (data.error) {
                    redditPosts.innerHTML = `<div class="reddit-error">${data.error}</div>`;
                    return;
                }

                if (!data.posts || data.posts.length === 0) {
                    redditPosts.innerHTML = `<div class="reddit-error">No posts found</div>`;
                    return;
                }

                redditPosts.innerHTML = '';
                data.posts.forEach(post => {
                    const postEl = createRedditPostElement(post);
                    redditPosts.appendChild(postEl);
                });

                redditLoaded = true;
            } catch (err) {
                console.error(err);
                redditPosts.innerHTML = `<div class="reddit-error">Failed to load posts. Check Reddit API credentials.</div>`;
            }
        }

        function createRedditPostElement(post) {
            const div = document.createElement('div');
            div.className = 'reddit-post';
            div.dataset.postId = post.id;

            const commentsHtml = post.top_comments.map((c, idx) => `
                <div class="reddit-comment" data-comment-idx="${idx}" data-comment-text="${escapeHtml(c.text)}" data-post-title="${escapeHtml(post.title)}">
                    <div class="reddit-comment-text">${escapeHtml(c.text)}</div>
                    <div class="reddit-comment-score">${c.score} points</div>
                </div>
            `).join('');

            div.innerHTML = `
                <div class="reddit-post-header">
                    <img class="reddit-post-image" src="${post.image_url}" alt="Post image" onerror="this.style.display='none'">
                    <div class="reddit-post-info">
                        <div class="reddit-post-title">${escapeHtml(post.title)}</div>
                        <div class="reddit-post-meta">${post.score} upvotes</div>
                        <a class="reddit-post-link" href="${post.permalink}" target="_blank">View on Reddit</a>
                    </div>
                </div>
                ${post.top_comments.length > 0 ? `
                    <div class="reddit-comments">
                        <div class="reddit-comments-title">Top comments (click to use as hook)</div>
                        ${commentsHtml}
                    </div>
                ` : ''}
                <textarea class="reddit-hook-input" placeholder="Enter hook text or click a comment above..." data-post-id="${post.id}"></textarea>
                <div class="reddit-post-actions">
                    <button class="btn btn-secondary rephrase-btn" data-post-id="${post.id}">Rephrase with AI</button>
                    <button class="btn btn-primary generate-btn" data-post-id="${post.id}" data-image-url="${post.image_url}">Generate Video</button>
                </div>
            `;

            // Comment click handlers
            div.querySelectorAll('.reddit-comment').forEach(commentEl => {
                commentEl.addEventListener('click', () => {
                    div.querySelectorAll('.reddit-comment').forEach(c => c.classList.remove('selected'));
                    commentEl.classList.add('selected');
                    const hookInput = div.querySelector('.reddit-hook-input');
                    hookInput.value = commentEl.dataset.commentText;
                });
            });

            // Rephrase button
            div.querySelector('.rephrase-btn').addEventListener('click', async () => {
                const hookInput = div.querySelector('.reddit-hook-input');
                const comment = hookInput.value;
                if (!comment) return;

                const btn = div.querySelector('.rephrase-btn');
                btn.disabled = true;
                btn.textContent = 'Rephrasing...';

                try {
                    const response = await fetch('/reddit/rephrase', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ comment, title: post.title })
                    });
                    const data = await response.json();
                    if (data.hook) {
                        hookInput.value = data.hook;
                    }
                } catch (err) {
                    console.error(err);
                }

                btn.disabled = false;
                btn.textContent = 'Rephrase with AI';
            });

            // Generate video button
            div.querySelector('.generate-btn').addEventListener('click', async () => {
                const hookInput = div.querySelector('.reddit-hook-input');
                const hook = hookInput.value;
                if (!hook) {
                    alert('Please enter or select a hook text first');
                    return;
                }

                const btn = div.querySelector('.generate-btn');
                const imageUrl = btn.dataset.imageUrl;

                btn.disabled = true;
                btn.textContent = 'Generating...';

                try {
                    const response = await fetch('/reddit/create-video', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ image_url: imageUrl, hook })
                    });

                    if (!response.ok) throw new Error('Failed to generate video');

                    const blob = await response.blob();
                    const url = URL.createObjectURL(blob);

                    // Create download link
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = `hook_${post.id}.mp4`;
                    a.click();

                    btn.textContent = 'Downloaded!';
                    setTimeout(() => {
                        btn.textContent = 'Generate Video';
                        btn.disabled = false;
                    }, 2000);
                } catch (err) {
                    console.error(err);
                    btn.textContent = 'Error';
                    setTimeout(() => {
                        btn.textContent = 'Generate Video';
                        btn.disabled = false;
                    }, 2000);
                }
            });

            return div;
        }

        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }

        refreshReddit.addEventListener('click', () => {
            redditLoaded = false;
            loadRedditPosts();
        });

        redditSort.addEventListener('change', () => {
            redditLoaded = false;
            loadRedditPosts();
        });
    </script>
</body>
</html>
"""


@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)


@app.route('/generate-hooks', methods=['POST'])
def generate_hooks():
    if 'image' not in request.files:
        return jsonify({'error': 'No image provided'}), 400

    file = request.files['image']
    if not file or not allowed_file(file.filename):
        return jsonify({'error': 'Invalid file type'}), 400

    # Save temporarily
    filename = secure_filename(f"{uuid.uuid4()}_{file.filename}")
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)

    try:
        # Describe image with vision model
        description = describe_image_with_llm(filepath)

        # Generate hooks based on description
        hooks = generate_hooks_with_llm(description)

        return jsonify({'hooks': hooks, 'description': description})
    except Exception as e:
        return jsonify({'error': str(e), 'hooks': [
            "When this hits different...",
            "POV: You finally understand...",
            "This is your sign to...",
            "Nobody talks about this but...",
            "The way this changed everything..."
        ]})


@app.route('/create-video', methods=['POST'])
def create_video_endpoint():
    if 'image' not in request.files:
        return jsonify({'error': 'No image provided'}), 400

    file = request.files['image']
    hook_text = request.form.get('hook', 'Your hook text here...')

    if not file or not allowed_file(file.filename):
        return jsonify({'error': 'Invalid file type'}), 400

    # Save image
    filename = secure_filename(f"{uuid.uuid4()}_{file.filename}")
    image_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(image_path)

    # Create video
    video_filename = f"{uuid.uuid4()}.mp4"
    video_path = os.path.join(app.config['UPLOAD_FOLDER'], video_filename)

    try:
        print(f"Creating video: {image_path} -> {video_path}")
        print(f"Hook: {hook_text}")
        create_video(image_path, hook_text, video_path)
        print(f"Video created successfully: {video_path}")
        return send_file(video_path, mimetype='video/mp4', as_attachment=True, download_name='tiktok_hook.mp4')
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Error creating video: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        # Cleanup image
        if os.path.exists(image_path):
            os.remove(image_path)


@app.route('/reddit/posts', methods=['GET'])
def get_reddit_posts():
    """Fetch posts from r/adhdmeme"""
    subreddit = request.args.get('subreddit', 'adhdmeme')
    sort = request.args.get('sort', 'hot')
    limit = min(int(request.args.get('limit', 10)), 25)

    result = fetch_reddit_posts(subreddit, sort, limit)
    return jsonify(result)


@app.route('/reddit/rephrase', methods=['POST'])
def rephrase_hook():
    """Rephrase a Reddit comment into a TikTok hook"""
    data = request.get_json()
    comment = data.get('comment', '')
    title = data.get('title', '')

    if not comment:
        return jsonify({'error': 'No comment provided'}), 400

    hook = rephrase_comment_as_hook(comment, title)
    return jsonify({'hook': hook})


@app.route('/reddit/create-video', methods=['POST'])
def create_video_from_reddit():
    """Download Reddit image and create video"""
    data = request.get_json()
    image_url = data.get('image_url', '')
    hook_text = data.get('hook', 'Your hook text here...')

    if not image_url:
        return jsonify({'error': 'No image URL provided'}), 400

    # Download image
    image_path = download_reddit_image(image_url)
    if not image_path:
        return jsonify({'error': 'Failed to download image'}), 500

    # Create video
    video_filename = f"{uuid.uuid4()}.mp4"
    video_path = os.path.join(app.config['UPLOAD_FOLDER'], video_filename)

    try:
        print(f"Creating video from Reddit: {image_url} -> {video_path}")
        print(f"Hook: {hook_text}")
        create_video(image_path, hook_text, video_path)
        print(f"Video created successfully: {video_path}")
        return send_file(video_path, mimetype='video/mp4', as_attachment=True, download_name='tiktok_hook.mp4')
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Error creating video: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        # Cleanup
        if os.path.exists(image_path):
            os.remove(image_path)


@app.route('/reddit/status', methods=['GET'])
def reddit_status():
    """Check if Apify API is configured for Reddit scraping"""
    return jsonify({
        'configured': bool(APIFY_API_TOKEN),
        'has_openrouter': bool(OPENROUTER_API_KEY)
    })


if __name__ == '__main__':
    port = int(os.getenv("PORT", 8080))
    debug = os.getenv("FLASK_ENV", "development") == "development"

    print("\n" + "=" * 50)
    print("TikTok Hook Video Generator")
    print("=" * 50)
    print(f"\nOpenRouter API: {'Configured' if OPENROUTER_API_KEY else 'Not set (using fallback hooks)'}")
    print(f"Apify API: {'Configured' if APIFY_API_TOKEN else 'Not set (Reddit tab disabled)'}")
    print(f"Font: {TIKTOK_FONT_BOLD or 'Default'}")
    print(f"\nStarting server at http://0.0.0.0:{port}")
    print("=" * 50 + "\n")

    app.run(debug=debug, host='0.0.0.0', port=port)
