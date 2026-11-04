#!/usr/bin/env bash
set -euo pipefail

cd /opt/worship_bot
export IMAGE_TAG="${1:?Pass a published image tag}"
[[ "$IMAGE_TAG" =~ ^[a-zA-Z0-9_.-]+$ ]]
compose=(docker compose -f compose.production.yaml)

# Keep the running version available if downloading new images fails.
"${compose[@]}" pull
mkdir -p backups
chmod 700 backups
umask 077
backup="backups/database-$(date +%Y%m%d-%H%M%S).dump"
"${compose[@]}" exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > "$backup"
test -s "$backup"

"${compose[@]}" stop bot push-worker
"${compose[@]}" up -d --wait --wait-timeout 300 api
"${compose[@]}" up -d --wait --wait-timeout 300 frontend push-worker bot gateway
"${compose[@]}" ps
