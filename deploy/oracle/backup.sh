#!/usr/bin/env bash
# Copy the SQLite database out of the container to ~/vayu-backups/vayu-<date>.db
# Add to cron for a daily backup:  0 3 * * * bash ~/vayu-aqi/deploy/oracle/backup.sh
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
OUT="$HOME/vayu-backups"
mkdir -p "$OUT"
STAMP="$(date +%Y%m%d-%H%M)"
cd "$DIR"
sudo docker compose exec -T app python -c "
import sqlite3
src = sqlite3.connect('/data/vayu.db')
dst = sqlite3.connect('/data/backup.db')
src.backup(dst)
dst.close()
"
sudo docker compose cp app:/data/backup.db "$OUT/vayu-$STAMP.db"
find "$OUT" -name "vayu-*.db" -printf "%T@ %p\n" | sort -rn | tail -n +15 | cut -d" " -f2- | xargs -r rm --   # keep the latest 14
echo "Saved $OUT/vayu-$STAMP.db"
