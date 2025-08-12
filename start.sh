#!/bin/bash

# JAIMES AI Executive - Startup Script
# This script handles startup for different deployment environments

set -e  # Exit on any error

echo "🚀 Starting JAIMES AI Executive..."

# Detect environment
if [ "$DEPLOY_ENV" = "prod" ] || [ "$RENDER" = "true" ]; then
    echo "📦 Production environment detected"
    MODE="production"
    PORT=${PORT:-8000}
elif [ "$DEPLOY_ENV" = "development" ]; then
    echo "🔧 Development environment detected"
    MODE="development"
    PORT=${PORT:-8000}
else
    echo "🧪 Testing environment detected"
    MODE="testing"
    PORT=${PORT:-8000}
fi

# Create necessary directories
mkdir -p logs data cache

# Download NLTK data if needed
echo "📚 Checking NLTK data..."
python -c "
import nltk
try:
    nltk.data.find('vader_lexicon')
    print('NLTK data already available')
except LookupError:
    print('Downloading NLTK data...')
    nltk.download('vader_lexicon', quiet=True)
    nltk.download('punkt', quiet=True)
    print('NLTK data downloaded successfully')
"

# Validate environment variables
echo "🔍 Validating environment..."
if [ -z "$GROQ_API_KEY" ]; then
    echo "⚠️  Warning: GROQ_API_KEY not set - running in demo mode"
fi

# Start the application
echo "🎯 Starting JAIMES on port $PORT in $MODE mode..."

if [ "$MODE" = "production" ]; then
    # Production: Use uvicorn with optimized settings
    exec uvicorn main:app \
        --host 0.0.0.0 \
        --port $PORT \
        --workers 1 \
        --loop uvloop \
        --http httptools \
        --access-log \
        --log-level info
elif [ "$MODE" = "development" ]; then
    # Development: Use uvicorn with reload
    exec uvicorn main:app \
        --host 0.0.0.0 \
        --port $PORT \
        --reload \
        --log-level debug
else
    # Testing: Use Python directly
    exec python main.py --mode testing --port $PORT
fi

