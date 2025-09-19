#!/bin/bash
set -e

# Start ngrok in background
ngrok http 8000 --log=stdout > /tmp/ngrok.log 2>&1 &

# Wait for ngrok to start
sleep 5

# Get and display the ngrok URL
echo "Fetching ngrok URL..."
NGROK_URL=$(curl -s http://localhost:4040/api/tunnels | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    if 'tunnels' in data and len(data['tunnels']) > 0:
        print(data['tunnels'][0]['public_url'])
    else:
        print('No tunnels found')
except:
    print('Error fetching ngrok URL')
" 2>/dev/null || echo "Could not fetch ngrok URL")

echo "Ngrok URL: $NGROK_URL"

# Start the main application
exec python app.py
