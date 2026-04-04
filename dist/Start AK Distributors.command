#!/bin/bash
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

echo "Starting AK Distributors..."
echo "Please wait..."

# Start the app in background
"$DIR/AK Distributors.app/Contents/MacOS/AKDistributors" &

# Wait for server to actually start by checking port
for i in {1..30}; do
    sleep 1
    if curl -s http://127.0.0.1:5000 > /dev/null 2>&1; then
        echo "App started!"
        break
    fi
    echo "Loading... ($i)"
done

# Open browser
open http://127.0.0.1:5000
