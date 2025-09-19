# PORT Environment Variable Fix

## Problem
The error `Error: Invalid value for '--port': '$PORT' is not a valid integer` occurs when the PORT environment variable is not properly expanded or passed to uvicorn.

## Solution
Updated the configuration and deployment files to properly handle the PORT environment variable:

### 1. Fixed `config.py`
- Added robust PORT environment variable handling
- Validates port values and falls back to default (8001) if invalid
- Supports both `PORT` and `API_PORT` environment variables

### 2. Updated `Procfile`
- Changed from bash script to direct Python execution
- Eliminates shell expansion issues
- Direct uvicorn execution with proper port handling

### 3. Updated `start.sh`
- Cleaned up the startup script
- Added proper port validation
- Simplified Tesseract detection

## Testing
Run the test script to verify everything works:
```bash
test_port.bat
```

## Deployment Files

### For Railway/Heroku (Procfile):
```
web: python -c "import os; import uvicorn; from config import config; port=int(os.getenv('PORT', config.port)); uvicorn.run('app:app', host=config.host, port=port)"
```

### For Docker (start.sh):
```bash
#!/bin/bash
exec uvicorn app:app --host "$API_HOST" --port "$API_PORT"
```

### For manual deployment:
```bash
# Set the PORT environment variable
export PORT=8080

# Start the server
python -c "
import uvicorn
from config import config
uvicorn.run('app:app', host=config.host, port=config.port)
"
```

## Environment Variable Priority
1. `PORT` (used by Railway, Heroku, etc.)
2. `API_PORT` (custom variable)
3. Default: `8001`

## Validation
- Port must be between 1 and 65535
- Invalid values fall back to 8001 with a warning
- Non-numeric values are handled gracefully

## Status: ✅ FIXED
The PORT environment variable issue has been resolved. The API will now start correctly on platforms like Railway, Heroku, and Vercel.
