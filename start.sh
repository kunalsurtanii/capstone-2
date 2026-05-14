#!/bin/bash
set -e

# Start Ollama server in the background
ollama serve &

echo "Waiting for Ollama to be ready..."
until curl -sf http://localhost:11434/api/version > /dev/null; do
    sleep 2
done
echo "Ollama is ready."

# Pull the model only if it hasn't been cached in the volume yet
if ! ollama list | grep -q "llama3"; then
    echo "Pulling llama3 model (this may take a few minutes on first run)..."
    ollama pull llama3
fi

mkdir -p /app/data
touch /app/data/history.db

echo "Starting Streamlit..."
exec streamlit run app.py \
    --server.port 8501 \
    --server.address 0.0.0.0 \
    --server.headless true
