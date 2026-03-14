set -e
printf 'FILE:\n'
sed -n '1,80p' ~/.config/strategos/strategos.env || true
printf '\n---\n'
set +e
set -a
source ~/.config/strategos/strategos.env
SRC_CODE=$?
set +a
set -e
printf 'SOURCE_EXIT=%s\n' "$SRC_CODE"
env | grep -E 'DATABASE_URL|SUPABASE|OPENCLAW|SECRET_KEY' || true