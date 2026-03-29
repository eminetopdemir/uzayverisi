#!/usr/bin/env bash
# deploy.sh — Build and deploy SatComm Monitor with Docker Compose
#
# Usage:  bash deploy.sh
#
set -e

echo ""
echo "🛰️  SatComm Monitor — Docker Deployment"
echo "──────────────────────────────────────────"

# Build images
echo "▶  Building Docker images..."
docker compose build

# Start services
echo "▶  Starting services..."
docker compose up -d

# Health check
echo ""
echo "⏳  Waiting for services to start..."
sleep 5

if docker compose ps | grep -q "Up"; then
    echo ""
    echo "✅  Deployment successful!"
    echo ""
    echo "   Frontend  →  http://$(hostname -I | awk '{print $1}')"
    echo "   Mobile    →  http://$(hostname -I | awk '{print $1}')/mobile"
    echo "   API docs  →  http://$(hostname -I | awk '{print $1}')/api/docs"
    echo ""
    echo "   Any device on the internet can access these URLs."
    echo ""
    docker compose ps
else
    echo "❌  Something went wrong. Check logs:"
    echo "   docker compose logs"
    exit 1
fi
