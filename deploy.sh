#!/bin/bash
set -e
echo "Deploying QQ bot to cloud..."
docker compose down
docker compose build --no-cache
docker compose up -d
echo "Deploy complete. Bot should be running."