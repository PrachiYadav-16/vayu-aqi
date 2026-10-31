#!/usr/bin/env bash
# Pull the latest code and rebuild. Data (users, trips, readings) lives in a
# Docker volume and is kept.
set -euo pipefail
DIR="$(cd "$(dirname "$0")/../.." && pwd)"
git -C "$DIR" pull --ff-only
cd "$DIR/deploy/oracle"
sudo docker compose up -d --build
sudo docker image prune -f >/dev/null
echo "Updated. Logs: sudo docker compose -f $DIR/deploy/oracle/docker-compose.yml logs -f app"
