set -e
cd ~/strategos-backend
source .venv/bin/activate
set -a
source ~/.config/strategos/strategos.env
set +a
python3 - <<'PY'
import os, psycopg
url=os.environ['DATABASE_URL']
with psycopg.connect(url) as conn:
    with conn.cursor() as cur:
        cur.execute("ALTER TABLE IF EXISTS alembic_version ALTER COLUMN version_num TYPE VARCHAR(128)")
        conn.commit()
print('ALTER_OK')
PY
alembic -c alembic.ini upgrade head
python scripts/seed_deterministic_baseline.py
systemctl --user restart strategos-backend
sleep 2
systemctl --user --no-pager status strategos-backend | head -n 50
