FROM python:3.11-slim

# Install system dependencies including ffmpeg
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libsm6 \
    libxext6 \
    fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt gunicorn

# Copy application code
COPY . .

# Create temp directory for uploads
RUN mkdir -p /tmp/uploads

# Expose port (Railway sets PORT env var)
EXPOSE 8080

# Run with gunicorn for production - use shell form to expand $PORT
CMD gunicorn --bind 0.0.0.0:${PORT:-8080} --timeout 120 --workers 2 app:app
