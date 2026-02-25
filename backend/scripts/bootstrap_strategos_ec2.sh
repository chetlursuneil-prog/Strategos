#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$HOME/strategos-backend"
ENV_FILE="$HOME/.config/strategos/strategos.env"
SERVICE_FILE="$HOME/.config/systemd/user/strategos-backend.service"

mkdir -p "$(dirname "$ENV_FILE")"
mkdir -p "$HOME/.config/systemd/user"

if [ ! -d "$APP_DIR" ]; then
  echo "ERROR: $APP_DIR not found"
  exit 1
fi

cd "$APP_DIR"

python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

if [ ! -f "$ENV_FILE" ]; then
  echo "ERROR: missing env file $ENV_FILE"
  exit 1
fi

set -a
while IFS='=' read -r key value; do
  key="${key%$'\r'}"
  value="${value%$'\r'}"
  if [ -z "$key" ] || [[ "$key" =~ ^\s*# ]]; then
    continue
  fi
  export "$key=$value"
done < "$ENV_FILE"
set +a

if [ -z "${DATABASE_URL:-}" ]; then
  echo "ERROR: DATABASE_URL is required"
  exit 1
fi

if [ -f "alembic.ini" ]; then
  alembic -c alembic.ini upgrade head
fi

if [ -f "scripts/seed_deterministic_baseline.py" ]; then
  python scripts/seed_deterministic_baseline.py || true
fi

cat > "$SERVICE_FILE" <<'UNIT'
[Unit]
Description=STRATEGOS Backend API
After=network-online.target

[Service]
Type=simple
WorkingDirectory=%h/strategos-backend
EnvironmentFile=%h/.config/strategos/strategos.env
ExecStart=%h/strategos-backend/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=2

[Install]
WantedBy=default.target
UNIT

systemctl --user daemon-reload
systemctl --user enable strategos-backend.service
systemctl --user restart strategos-backend.service

sleep 2
systemctl --user status strategos-backend.service --no-pager || true
curl -sS http://127.0.0.1:8000/api/v1/health || true

echo "STRATEGOS backend bootstrap complete"