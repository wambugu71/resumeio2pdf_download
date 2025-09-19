# Docker Deployment Guide

This comprehensive Docker setup includes ngrok, Tesseract OCR, and all dependencies for the Resume PDF Generator API.

## Quick Start

### Option 1: Basic API (no ngrok)
```bash
start_docker_basic.bat
```

### Option 2: API with ngrok tunnel
```bash
start_docker_ngrok.bat
```

### Option 3: Full Docker management
```bash
docker_manager.bat
```

## What's Included

The Dockerfile installs:
- ✅ **Python 3.11** with all required packages
- ✅ **Tesseract OCR** with multiple languages (English, French, German, Spanish)
- ✅ **ngrok** for public tunneling
- ✅ **Image processing libraries** (OpenCV, PIL dependencies)
- ✅ **Network tools** (curl, wget)
- ✅ **Process management** (supervisor for multi-process)

## Docker Services

### 1. `resume-pdf-api` (Basic)
- **Purpose**: Standard API without ngrok
- **Ports**: 8001
- **Start**: `docker-compose up -d resume-pdf-api`
- **Access**: http://localhost:8001

### 2. `api-with-ngrok` (Tunneled)
- **Purpose**: API with ngrok public tunnel
- **Ports**: 8001 (API), 4040 (ngrok web UI)
- **Requirements**: ngrok auth token in .env
- **Start**: `docker-compose --profile ngrok up -d api-with-ngrok`

### 3. `api-dev` (Development)
- **Purpose**: Development with auto-reload
- **Features**: Live code reload, debug mode
- **Start**: `docker-compose --profile dev up api-dev`

## Environment Setup

### 1. Set up ngrok (for tunnel)
1. Get your auth token from: https://dashboard.ngrok.com/get-started/your-authtoken
2. Edit `.env` file:
   ```bash
   NGROK_AUTH_TOKEN=your_actual_token_here
   ```

### 2. Build the image
```bash
docker build -t resume-pdf-api .
```

## Available Scripts

### Start Scripts
- `start_docker_basic.bat` - Start basic API
- `start_docker_ngrok.bat` - Start with ngrok tunnel
- `docker_manager.bat` - Full management interface

### Manual Commands

#### Build and run basic API:
```bash
docker build -t resume-pdf-api .
docker-compose up -d resume-pdf-api
```

#### Build and run with ngrok:
```bash
docker build -t resume-pdf-api .
docker-compose --profile ngrok up -d api-with-ngrok
```

#### Development mode:
```bash
docker-compose --profile dev up api-dev
```

## API Endpoints

Once running, access these endpoints:

- **API Root**: http://localhost:8001/
- **Health Check**: http://localhost:8001/health
- **API Documentation**: http://localhost:8001/docs
- **Generate PDF**: POST http://localhost:8001/generate-pdf
- **Test Endpoint**: POST http://localhost:8001/double

### With ngrok tunnel:
- **ngrok Web UI**: http://localhost:4040
- **Public URL**: Check ngrok logs or web UI

## Docker Image Features

### Startup Scripts
- `/app/start.sh` - Default startup (with optional ngrok)
- `/app/start_with_ngrok.sh` - Force ngrok tunnel
- `/app/start_dev.sh` - Development mode with reload

### Paths and Configuration
- **Tesseract**: `/usr/bin/tesseract`
- **ngrok**: `/usr/local/bin/ngrok`
- **App**: `/app`
- **Logs**: `/app/logs`

### Languages Supported by Tesseract
- English (eng)
- French (fra) 
- German (deu)
- Spanish (spa)

## Usage Examples

### Test the API with curl:

```bash
# Health check
curl http://localhost:8001/health

# Test endpoint
curl -X POST "http://localhost:8001/double" \
  -H "Content-Type: application/json" \
  -d '{"value": 5}'

# Generate PDF (replace with actual token)
curl -X POST "http://localhost:8001/generate-pdf" \
  -H "Content-Type: application/json" \
  -d '{"access_token": "your-token", "resolution": 3000}' \
  --output resume.pdf
```

### With ngrok tunnel:
```bash
# Replace abc123.ngrok.io with your actual ngrok URL
curl -X POST "https://abc123.ngrok.io/generate-pdf" \
  -H "Content-Type: application/json" \
  -d '{"access_token": "your-token", "resolution": 3000}' \
  --output resume.pdf
```

## Troubleshooting

### Container won't start
```bash
# Check logs
docker logs resume-pdf-generator

# Check if port is busy
netstat -an | findstr :8001
```

### ngrok issues
```bash
# Check ngrok logs
docker logs resume-pdf-ngrok

# Verify auth token
docker exec resume-pdf-ngrok ngrok config check
```

### Tesseract issues
```bash
# Test Tesseract in container
docker exec resume-pdf-generator tesseract --version

# Check available languages
docker exec resume-pdf-generator tesseract --list-langs
```

### Build issues
```bash
# Clean rebuild
docker system prune -f
docker build --no-cache -t resume-pdf-api .
```

## File Structure

```
pythonbackend/
├── Dockerfile                    # Main Docker configuration
├── docker-compose.yml           # Multi-service configuration
├── .env                         # Environment variables
├── start_docker_basic.bat       # Quick start basic API
├── start_docker_ngrok.bat       # Quick start with ngrok
├── docker_manager.bat           # Full Docker management
├── requirements.txt             # Python dependencies
├── app.py                       # FastAPI application
├── config.py                    # Configuration
└── logs/                        # Container logs (created at runtime)
```

## Performance Notes

- **Memory**: ~500MB per container
- **CPU**: Optimized for PDF processing
- **Storage**: ~2GB image size
- **Startup**: ~10-15 seconds

## Production Deployment

For production, consider:
1. Remove development tools
2. Use multi-stage build
3. Run as non-root user
4. Set up proper logging
5. Use Docker secrets for tokens
6. Set up health checks and monitoring
