#!/bin/bash

echo "========================================"
echo "🚀 Starting PW-Extractor Bot"
echo "========================================"

# Check Python version
echo "📌 Python Version:"
python --version

# Install dependencies
echo "📦 Installing dependencies..."
pip install -r requirements.txt --quiet

# Start the bot
echo "🤖 Starting Bot..."
python main.py
