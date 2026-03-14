#!/usr/bin/env bash
set -euo pipefail

MODE="${1:-status}"
ENV_FILE="${STRATEGOS_ENV_FILE:-$HOME/.config/strategos/strategos.env}"
BACKUP_FILE="${STRATEGOS_MODE_BACKUP_FILE:-$HOME/.config/strategos/strategos.integrated.backup.env}"
SERVICE_NAME="${STRATEGOS_SERVICE_NAME:-strategos-backend}"

RELEVANT_KEYS=(
  OPENCLAW_EXECUTION_MODE
  OPENCLAW_ALLOW_DETERMINISTIC_FALLBACK
  OPENCLAW_API_BASE_URL
  OPENCLAW_API_AGENT_PATH
  OPENCLAW_API_AUTH_TOKEN
  OPENCLAW_API_TIMEOUT_SECONDS
  OPENCLAW_AGENT_TIMEOUT_SECONDS
  OPENCLAW_ENABLE_WS_FALLBACK
  OPENCLAW_MAX_PARALLEL_AGENTS
  OPENCLAW_REMOTE_RETRIES
)

ensure_env_file() {
  mkdir -p "$(dirname "$ENV_FILE")"
  touch "$ENV_FILE"
}

upsert_kv() {
  local key="$1"
  local value="$2"
  if grep -q "^${key}=" "$ENV_FILE"; then
    sed -i "s|^${key}=.*|${key}=${value}|" "$ENV_FILE"
  else
    echo "${key}=${value}" >> "$ENV_FILE"
  fi
}

capture_integrated_backup() {
  mkdir -p "$(dirname "$BACKUP_FILE")"
  : > "$BACKUP_FILE"
  for key in "${RELEVANT_KEYS[@]}"; do
    local line
    line="$(grep -E "^${key}=" "$ENV_FILE" || true)"
    if [[ -n "$line" ]]; then
      echo "$line" >> "$BACKUP_FILE"
    fi
  done
}

restore_integrated_backup() {
  if [[ ! -s "$BACKUP_FILE" ]]; then
    echo "No integrated backup found at: $BACKUP_FILE"
    echo "Applying minimal integrated defaults only."
    upsert_kv "OPENCLAW_EXECUTION_MODE" "remote_http"
    upsert_kv "OPENCLAW_ALLOW_DETERMINISTIC_FALLBACK" "true"
    return
  fi

  while IFS= read -r line; do
    [[ -z "$line" ]] && continue
    local key="${line%%=*}"
    local value="${line#*=}"
    upsert_kv "$key" "$value"
  done < "$BACKUP_FILE"
}

restart_backend() {
  systemctl --user daemon-reload || true
  systemctl --user restart "${SERVICE_NAME}.service"
  systemctl --user is-active "${SERVICE_NAME}.service" >/dev/null
}

print_status() {
  local current_mode
  current_mode="$(grep -E '^OPENCLAW_EXECUTION_MODE=' "$ENV_FILE" | tail -n1 | cut -d'=' -f2- || true)"
  if [[ "$current_mode" == "deterministic_fallback" || "$current_mode" == "fallback" ]]; then
    echo "mode=strategos-only"
  else
    echo "mode=integrated"
  fi
  echo "env_file=$ENV_FILE"
  echo "backup_file=$BACKUP_FILE"
  grep -E '^OPENCLAW_(EXECUTION_MODE|ALLOW_DETERMINISTIC_FALLBACK|API_BASE_URL|API_AGENT_PATH|API_TIMEOUT_SECONDS|AGENT_TIMEOUT_SECONDS|ENABLE_WS_FALLBACK|MAX_PARALLEL_AGENTS|REMOTE_RETRIES)=' "$ENV_FILE" || true
}

switch_to_strategos_only() {
  capture_integrated_backup
  upsert_kv "OPENCLAW_EXECUTION_MODE" "deterministic_fallback"
  upsert_kv "OPENCLAW_ALLOW_DETERMINISTIC_FALLBACK" "true"
  restart_backend
  print_status
}

switch_to_integrated() {
  restore_integrated_backup
  restart_backend
  print_status
}

ensure_env_file

case "$MODE" in
  strategos-only|strategos_only|fallback)
    switch_to_strategos_only
    ;;
  integrated|normal|remote_http)
    switch_to_integrated
    ;;
  status)
    print_status
    ;;
  *)
    echo "Usage: $0 {strategos-only|integrated|status}" >&2
    exit 1
    ;;
esac

