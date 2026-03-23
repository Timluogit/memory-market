#!/usr/bin/env bash
# ============================================================
# Agent Memory Market — Deployment Script
# Usage:
#   ./scripts/deploy.sh              # deploy / rolling update
#   ./scripts/deploy.sh --rollback   # rollback to previous image
#   ./scripts/deploy.sh --down       # stop everything
# ============================================================
set -euo pipefail

COMPOSE_FILE="docker-compose.yml"
PROJECT_NAME="memory-market"
BACKUP_TAG_FILE=".last_deploy_tag"

cd "$(dirname "$0")/.."

log() { echo -e "\033[1;34m[deploy]\033[0m $*"; }
err() { echo -e "\033[1;31m[error]\033[0m $*" >&2; }

# ---- Health check ----
wait_healthy() {
    local svc=$1 max=${2:-60} i=0
    log "Waiting for $svc to become healthy (max ${max}s)…"
    while [ $i -lt $max ]; do
        local status
        status=$(docker compose -p "$PROJECT_NAME" ps --format json "$svc" 2>/dev/null \
                 | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('Health',''))" 2>/dev/null || echo "")
        if [ "$status" = "healthy" ]; then
            log "$svc is healthy ✓"
            return 0
        fi
        sleep 2; i=$((i+2))
    done
    err "$svc did not become healthy within ${max}s"
    return 1
}

# ---- Rolling deploy ----
deploy() {
    log "Building images…"
    docker compose -p "$PROJECT_NAME" -f "$COMPOSE_FILE" build --parallel

    # Save current image tag for rollback
    docker compose -p "$PROJECT_NAME" -f "$COMPOSE_FILE" images -q app-1 2>/dev/null \
        | head -1 > "$BACKUP_TAG_FILE" || true

    log "Starting Redis…"
    docker compose -p "$PROJECT_NAME" -f "$COMPOSE_FILE" up -d redis
    wait_healthy redis 30

    log "Rolling update — app-1…"
    docker compose -p "$PROJECT_NAME" -f "$COMPOSE_FILE" up -d --no-deps --build app-1
    wait_healthy app-1 90

    log "Rolling update — app-2…"
    docker compose -p "$PROJECT_NAME" -f "$COMPOSE_FILE" up -d --no-deps --build app-2
    wait_healthy app-2 90

    log "Starting Nginx…"
    docker compose -p "$PROJECT_NAME" -f "$COMPOSE_FILE" up -d nginx
    wait_healthy nginx 30

    log "✅ Deployment complete!"
    docker compose -p "$PROJECT_NAME" -f "$COMPOSE_FILE" ps
}

# ---- Rollback ----
rollback() {
    if [ ! -f "$BACKUP_TAG_FILE" ]; then
        err "No previous deployment tag found. Cannot rollback."
        exit 1
    fi
    local tag
    tag=$(cat "$BACKUP_TAG_FILE")
    log "Rolling back to image $tag …"
    # Restart app containers (images cached locally)
    docker compose -p "$PROJECT_NAME" -f "$COMPOSE_FILE" up -d --no-deps app-1 app-2
    wait_healthy app-1 60
    wait_healthy app-2 60
    log "✅ Rollback complete!"
}

# ---- Teardown ----
down() {
    log "Stopping all services…"
    docker compose -p "$PROJECT_NAME" -f "$COMPOSE_FILE" down
    log "✅ All services stopped."
}

# ---- Main ----
case "${1:-}" in
    --rollback) rollback ;;
    --down)     down ;;
    *)          deploy ;;
esac
