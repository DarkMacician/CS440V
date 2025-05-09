#!/bin/bash

# Function to handle cleanup on exit
cleanup() {
    echo "Stopping client..."
    # Kill the Streamlit process if it's running
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

# Run the client with auto-reload
echo "Starting client with auto-reload..."
streamlit run frontend.py --server.runOnSave=true --server.headless=true &
PID=$!

# Wait for the client process
wait $PID 