#!/bin/bash

# Function to handle cleanup on exit
cleanup() {
    echo "Stopping server..."
    # Kill the Python process if it's running
    if [ ! -z "$PID" ]; then
        kill $PID 2>/dev/null
    fi
    exit 0
}

# Set up signal handling
trap cleanup SIGINT SIGTERM

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install requirements if requirements.txt exists
if [ -f "requirements.txt" ]; then
    echo "Installing requirements..."
    pip install -r requirements.txt
fi

# Run the server
echo "Starting server..."
python server.py &
PID=$!

# Wait for the server process
wait $PID 