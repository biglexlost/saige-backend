#!/bin/bash

# JAIMES AI Executive - Deployment Utility Script
# Helps with various deployment scenarios

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[JAIMES]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Help function
show_help() {
    echo "JAIMES AI Executive - Deployment Script"
    echo ""
    echo "Usage: ./deploy.sh [COMMAND]"
    echo ""
    echo "Commands:"
    echo "  local       - Build and run locally with Docker"
    echo "  render      - Prepare for Render.com deployment"
    echo "  minipc      - Prepare for mini-PC deployment"
    echo "  test        - Run in testing mode"
    echo "  clean       - Clean up Docker containers and images"
    echo "  logs        - Show application logs"
    echo "  health      - Check application health"
    echo "  help        - Show this help message"
    echo ""
}

# Local Docker deployment
deploy_local() {
    print_status "Deploying JAIMES locally with Docker..."
    
    # Check if Docker is running
    if ! docker info > /dev/null 2>&1; then
        print_error "Docker is not running. Please start Docker first."
        exit 1
    fi
    
    # Build and run
    print_status "Building Docker image..."
    docker build -t jaimes-ai-executive .
    
    print_status "Starting JAIMES container..."
    docker run -d \
        --name jaimes \
        -p 8000:8000 \
        --env-file .env \
        --restart unless-stopped \
        jaimes-ai-executive
    
    print_success "JAIMES is running at http://localhost:8000"
    print_status "Use './deploy.sh logs' to view logs"
}

# Render.com preparation
prepare_render() {
    print_status "Preparing for Render.com deployment..."
    
    # Check required files
    if [ ! -f "render.yaml" ]; then
        print_error "render.yaml not found!"
        exit 1
    fi
    
    if [ ! -f "requirements-render.txt" ]; then
        print_error "requirements-render.txt not found!"
        exit 1
    fi
    
    print_success "Render deployment files are ready!"
    print_status "Next steps:"
    echo "  1. Push your code to GitHub"
    echo "  2. Connect your GitHub repo to Render"
    echo "  3. Set environment variables in Render dashboard:"
    echo "     - GROQ_API_KEY"
    echo "     - GROQ_MODEL"
    echo "     - UPSTASH_REDIS_REST_URL"
    echo "     - UPSTASH_REDIS_REST_TOKEN"
    echo "     - VAPI_API_KEY"
    echo "  4. Deploy!"
}

# Mini-PC deployment
prepare_minipc() {
    print_status "Preparing for mini-PC deployment..."
    
    # Create deployment package
    print_status "Creating mini-PC deployment package..."
    
    # Create a deployment directory
    mkdir -p minipc-deployment
    
    # Copy necessary files
    cp -r core_system minipc-deployment/
    cp -r api_integrations minipc-deployment/
    cp main.py minipc-deployment/
    cp config.py minipc-deployment/
    cp requirements-docker.txt minipc-deployment/requirements.txt
    cp start.sh minipc-deployment/
    cp docker-compose.yml minipc-deployment/
    cp Dockerfile minipc-deployment/
    cp .env.example minipc-deployment/
    
    # Create mini-PC specific instructions
    cat > minipc-deployment/MINIPC_SETUP.md << 'EOF'
# JAIMES Mini-PC Setup Instructions

## Prerequisites
1. Install Docker and Docker Compose
2. Ensure internet connectivity
3. Have your API keys ready

## Setup Steps
1. Copy this entire folder to your mini-PC
2. Copy `.env.example` to `.env` and fill in your API keys
3. Run: `docker-compose up -d`
4. Access JAIMES at `http://localhost:8000`

## Management Commands
- Start: `docker-compose up -d`
- Stop: `docker-compose down`
- Logs: `docker-compose logs -f`
- Update: `docker-compose pull && docker-compose up -d`

## Troubleshooting
- Check logs: `docker-compose logs jaimes`
- Restart: `docker-compose restart jaimes`
- Full reset: `docker-compose down -v && docker-compose up -d`
EOF
    
    print_success "Mini-PC deployment package created in 'minipc-deployment/' directory"
    print_status "Copy this entire directory to your mini-PC and follow MINIPC_SETUP.md"
}

# Test mode
run_test() {
    print_status "Running JAIMES in test mode..."
    python main.py --mode testing --demo
}

# Clean up Docker
clean_docker() {
    print_status "Cleaning up Docker containers and images..."
    
    # Stop and remove container
    docker stop jaimes 2>/dev/null || true
    docker rm jaimes 2>/dev/null || true
    
    # Remove image
    docker rmi jaimes-ai-executive 2>/dev/null || true
    
    print_success "Docker cleanup completed"
}

# Show logs
show_logs() {
    if docker ps | grep -q jaimes; then
        print_status "Showing JAIMES logs (Ctrl+C to exit)..."
        docker logs -f jaimes
    else
        print_error "JAIMES container is not running"
    fi
}

# Health check
check_health() {
    print_status "Checking JAIMES health..."
    
    if curl -f http://localhost:8000/health > /dev/null 2>&1; then
        print_success "JAIMES is healthy and responding"
    else
        print_error "JAIMES is not responding or not running"
        print_status "Try: ./deploy.sh logs"
    fi
}

# Main script logic
case "${1:-help}" in
    local)
        deploy_local
        ;;
    render)
        prepare_render
        ;;
    minipc)
        prepare_minipc
        ;;
    test)
        run_test
        ;;
    clean)
        clean_docker
        ;;
    logs)
        show_logs
        ;;
    health)
        check_health
        ;;
    help|*)
        show_help
        ;;
esac

