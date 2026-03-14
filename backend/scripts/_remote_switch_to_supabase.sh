set -e
cd ~/strategos-backend
source .venv/bin/activate
set -a
source ~/.config/strategos/strategos.env
set +a
python3 - <<'PY'
import os
print('DB_SET', bool(os.getenv('DATABASE_URL')))
PY
alembic -c alembic.ini upgrade head
python scripts/seed_deterministic_baseline.py
systemctl --user restart strategos-backend
sleep 2
systemctl --user --no-pager status strategos-backend | head -n 50
