"""
TikTok Hook Video Generator - Web App

Upload an image, generate hooks with AI (OpenRouter), and create TikTok-style videos.
"""

import os
import uuid
import tempfile
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

# TikTok Sans font
TIKTOK_FONT_BOLD = os.path.expanduser("~/Downloads/TikTok_Sans/static/TikTokSans-Bold.ttf")

# Video dimensions (9:16 TikTok)
VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1920

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def get_font(size):
    try:
        return ImageFont.truetype(TIKTOK_FONT_BOLD, size)
    except:
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
        bitrate="8000k",
        verbose=False,
        logger=None
    )

    return output_path


# HTML Template
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>TikTok Hook Video Generator</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #0f0f0f;
            color: #fff;
            min-height: 100vh;
            padding: 20px;
        }
        .container {
            max-width: 800px;
            margin: 0 auto;
        }
        h1 {
            text-align: center;
            margin-bottom: 30px;
            font-size: 2rem;
        }
        .upload-area {
            border: 2px dashed #333;
            border-radius: 12px;
            padding: 40px;
            text-align: center;
            cursor: pointer;
            transition: border-color 0.3s;
            margin-bottom: 20px;
        }
        .upload-area:hover { border-color: #fe2c55; }
        .upload-area.dragover { border-color: #fe2c55; background: rgba(254, 44, 85, 0.1); }
        #preview {
            max-width: 100%;
            max-height: 300px;
            border-radius: 8px;
            display: none;
            margin: 20px auto;
        }
        .hooks-container {
            margin: 20px 0;
            display: none;
        }
        .hook-option {
            background: #1a1a1a;
            border: 2px solid #333;
            border-radius: 8px;
            padding: 15px;
            margin: 10px 0;
            cursor: pointer;
            transition: all 0.3s;
        }
        .hook-option:hover { border-color: #fe2c55; }
        .hook-option.selected { border-color: #fe2c55; background: rgba(254, 44, 85, 0.1); }
        .custom-hook {
            width: 100%;
            background: #1a1a1a;
            border: 2px solid #333;
            border-radius: 8px;
            padding: 15px;
            color: #fff;
            font-size: 16px;
            resize: vertical;
            min-height: 80px;
            margin: 10px 0;
        }
        .custom-hook:focus { outline: none; border-color: #fe2c55; }
        .btn {
            background: #fe2c55;
            color: #fff;
            border: none;
            padding: 15px 30px;
            border-radius: 8px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            width: 100%;
            margin: 10px 0;
            transition: opacity 0.3s;
        }
        .btn:hover { opacity: 0.9; }
        .btn:disabled { opacity: 0.5; cursor: not-allowed; }
        .btn-secondary {
            background: #333;
        }
        .loading {
            display: none;
            text-align: center;
            padding: 20px;
        }
        .spinner {
            border: 3px solid #333;
            border-top: 3px solid #fe2c55;
            border-radius: 50%;
            width: 40px;
            height: 40px;
            animation: spin 1s linear infinite;
            margin: 0 auto 10px;
        }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
        .result { display: none; text-align: center; margin-top: 20px; }
        .result video {
            max-width: 300px;
            border-radius: 12px;
            margin: 20px 0;
        }
        input[type="file"] { display: none; }
        .section-title {
            font-size: 1.1rem;
            margin: 20px 0 10px;
            color: #888;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🎬 TikTok Hook Video Generator</h1>

        <div class="upload-area" id="uploadArea">
            <p>📷 Drop image here or click to upload</p>
            <p style="color: #666; font-size: 14px; margin-top: 10px;">PNG, JPG, GIF up to 16MB</p>
            <input type="file" id="fileInput" accept="image/*">
        </div>

        <img id="preview" alt="Preview">

        <div class="hooks-container" id="hooksContainer">
            <p class="section-title">✨ AI-Generated Hooks (click to select)</p>
            <div id="hooksList"></div>

            <p class="section-title">✏️ Or write your own</p>
            <textarea class="custom-hook" id="customHook" placeholder="Write your custom hook text here..."></textarea>

            <button class="btn" id="generateBtn" disabled>🎬 Generate Video</button>
        </div>

        <div class="loading" id="loading">
            <div class="spinner"></div>
            <p id="loadingText">Processing...</p>
        </div>

        <div class="result" id="result">
            <h2>✅ Video Ready!</h2>
            <video id="videoPreview" controls></video>
            <br>
            <a id="downloadLink" class="btn" download>📥 Download Video</a>
            <button class="btn btn-secondary" onclick="location.reload()">🔄 Create Another</button>
        </div>
    </div>

    <script>
        const uploadArea = document.getElementById('uploadArea');
        const fileInput = document.getElementById('fileInput');
        const preview = document.getElementById('preview');
        const hooksContainer = document.getElementById('hooksContainer');
        const hooksList = document.getElementById('hooksList');
        const customHook = document.getElementById('customHook');
        const generateBtn = document.getElementById('generateBtn');
        const loading = document.getElementById('loading');
        const loadingText = document.getElementById('loadingText');
        const result = document.getElementById('result');

        let uploadedFile = null;
        let selectedHook = '';

        // Drag and drop
        uploadArea.addEventListener('dragover', (e) => {
            e.preventDefault();
            uploadArea.classList.add('dragover');
        });
        uploadArea.addEventListener('dragleave', () => uploadArea.classList.remove('dragover'));
        uploadArea.addEventListener('drop', (e) => {
            e.preventDefault();
            uploadArea.classList.remove('dragover');
            handleFile(e.dataTransfer.files[0]);
        });
        uploadArea.addEventListener('click', () => fileInput.click());
        fileInput.addEventListener('change', (e) => handleFile(e.target.files[0]));

        async function handleFile(file) {
            if (!file || !file.type.startsWith('image/')) return;

            uploadedFile = file;
            preview.src = URL.createObjectURL(file);
            preview.style.display = 'block';
            uploadArea.style.display = 'none';

            // Generate hooks
            loading.style.display = 'block';
            loadingText.textContent = 'Analyzing image & generating hooks...';

            const formData = new FormData();
            formData.append('image', file);

            try {
                const response = await fetch('/generate-hooks', {
                    method: 'POST',
                    body: formData
                });
                const data = await response.json();

                hooksList.innerHTML = '';
                data.hooks.forEach(hook => {
                    const div = document.createElement('div');
                    div.className = 'hook-option';
                    div.textContent = hook;
                    div.onclick = () => selectHook(div, hook);
                    hooksList.appendChild(div);
                });

                loading.style.display = 'none';
                hooksContainer.style.display = 'block';
            } catch (err) {
                console.error(err);
                loading.style.display = 'none';
                hooksContainer.style.display = 'block';
            }
        }

        function selectHook(element, hook) {
            document.querySelectorAll('.hook-option').forEach(el => el.classList.remove('selected'));
            element.classList.add('selected');
            selectedHook = hook;
            customHook.value = '';
            generateBtn.disabled = false;
        }

        customHook.addEventListener('input', () => {
            if (customHook.value.trim()) {
                document.querySelectorAll('.hook-option').forEach(el => el.classList.remove('selected'));
                selectedHook = customHook.value.trim();
                generateBtn.disabled = false;
            } else if (!document.querySelector('.hook-option.selected')) {
                generateBtn.disabled = true;
            }
        });

        generateBtn.addEventListener('click', async () => {
            const hookText = customHook.value.trim() || selectedHook;
            if (!uploadedFile || !hookText) return;

            hooksContainer.style.display = 'none';
            loading.style.display = 'block';
            loadingText.textContent = 'Creating your video...';

            const formData = new FormData();
            formData.append('image', uploadedFile);
            formData.append('hook', hookText);

            try {
                const response = await fetch('/create-video', {
                    method: 'POST',
                    body: formData
                });

                if (!response.ok) throw new Error('Video creation failed');

                const blob = await response.blob();
                const url = URL.createObjectURL(blob);

                document.getElementById('videoPreview').src = url;
                document.getElementById('downloadLink').href = url;
                document.getElementById('downloadLink').download = 'tiktok_hook.mp4';

                loading.style.display = 'none';
                result.style.display = 'block';
            } catch (err) {
                console.error(err);
                alert('Error creating video. Please try again.');
                loading.style.display = 'none';
                hooksContainer.style.display = 'block';
            }
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
        create_video(image_path, hook_text, video_path)
        return send_file(video_path, mimetype='video/mp4', as_attachment=True, download_name='tiktok_hook.mp4')
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        # Cleanup image
        if os.path.exists(image_path):
            os.remove(image_path)


if __name__ == '__main__':
    print("\n" + "=" * 50)
    print("TikTok Hook Video Generator")
    print("=" * 50)
    print(f"\nOpenRouter API: {'✓ Configured' if OPENROUTER_API_KEY else '✗ Not set (using fallback hooks)'}")
    print("\nStarting server at http://localhost:5000")
    print("=" * 50 + "\n")

    app.run(debug=True, port=5000)
