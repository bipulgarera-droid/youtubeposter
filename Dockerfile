FROM python:3.11-slim

# Install system dependencies including fonts for subtitles
RUN apt-get update && apt-get install -y \
    ffmpeg \
    git \
    fonts-dejavu-core \
    fonts-freefont-ttf \
    libass9 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements first for caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create tmp directories
RUN mkdir -p .tmp/audio .tmp/images .tmp/video .tmp/stock

# Expose port
EXPOSE 5001

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:5001/health || exit 1

# Run the application
CMD ["python", "app.py"]
