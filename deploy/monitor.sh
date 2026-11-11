#!/bin/sh
# Schedule every 5 minutes. Forward nonzero exit and JSON output to your alerting system.
set -eu
cd "$(dirname "$0")"
docker compose --env-file .env.production -f compose.production.yml exec -T api python -m app.operations
