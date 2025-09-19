# Use Ubuntu 22.04 as base image
FROM ubuntu:22.04

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive \
    TZ=UTC

# Set work directory
WORKDIR /app

# Update and install system dependencies
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-dev \
    tesseract-ocr \
    libtesseract-dev \
    tesseract-ocr-eng \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    wget \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create symlink for python command
RUN ln -s /usr/bin/python3 /usr/bin/python

# Install ngrok
# Upgrade pip
RUN python3 -m pip install --upgrade pip

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose the port
EXPOSE 8080

# Tunnel port 8080 (where your app is actually running)
ENTRYPOINT ["sh", "-c", "gunicorn app:app -k uvicorn.workers.UvicornWorker --workers 2 --bind 0.0.0.0:8080"]
