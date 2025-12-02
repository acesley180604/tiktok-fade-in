# TikTok Hook Video Generator

Web app to create TikTok-style hook videos with AI-generated text.

## Features

- 🎬 **9:16 vertical format** (1080x1920) optimized for TikTok/Reels
- 🤖 **AI-powered hook generation** using OpenRouter (Llama 3.2 Vision)
- ✨ **Full-width text overlay** at top with TikTok Sans font
- 🌅 **2s black screen + 3s fade-in** effect
- 📤 **Upload any image** and get instant video output

## Video Structure

| Time | Effect |
|------|--------|
| 0-2s | Black screen + hook text at top (full-width white box) |
| 2-5s | Image fades in at center (full width, 3-second fade) |

## Installation

1. Clone the repo:
```bash
git clone https://github.com/acesley180604/tiktok-fade-in.git
cd tiktok-fade-in
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. (Optional) Set up OpenRouter API for AI hooks:
```bash
cp .env.example .env
# Edit .env and add your OPENROUTER_API_KEY
```

4. Download TikTok Sans font and place in `~/Downloads/TikTok_Sans/`

## Usage

### Start the Web App

```bash
python app.py
```

Then open http://localhost:5000 in your browser.

### How it works

1. **Upload an image** (meme, screenshot, photo)
2. **AI analyzes the image** and generates 5 hook options
3. **Select a hook** or write your own
4. **Click Generate** → Download your TikTok-ready video!

## OpenRouter Setup (Optional)

For AI-powered hook generation:

1. Get API key from https://openrouter.ai/keys
2. Set environment variable:
```bash
export OPENROUTER_API_KEY=your_key_here
```

Without an API key, the app will use fallback generic hooks.

## CLI Usage (Legacy)

```bash
python image_hook_builder.py <image.jpg> "Your hook text" [output.mp4]
```
