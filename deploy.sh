#!/bin/bash
set -e

echo "🚀 Deploying Isarwasser..."

# Pull latest code
echo "📥 Pulling latest code from GitHub..."
git pull origin main

# Rebuild and restart containers
echo "🔨 Building Docker images..."
docker-compose build --no-cache

echo "🔄 Restarting containers..."
docker-compose down
docker-compose up -d

# Show logs
echo "📋 Container status:"
docker-compose ps

echo "✅ Deployment complete!"
echo ""
echo "📊 View logs:"
echo "  docker-compose logs -f web"
echo "  docker-compose logs -f pipeline"
