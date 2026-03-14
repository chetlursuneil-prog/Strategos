import os
import psycopg
from pathlib import Path

env = Path('/home/ubuntu/.config/strategos/strategos.env')
for line in env.read_text().splitlines():
    s=line.strip()
    if not s or s.startswith('#') or '=' not in s:
        continue
    k,v=s.split('=',1)
    os.environ[k]=v

url=os.environ.get('DATABASE_URL')
print('DB_URL_SET', bool(url))
with psycopg.connect(url, connect_timeout=10) as conn:
    with conn.cursor() as cur:
        cur.execute('select version_num from alembic_version')
        print('ALEMBIC', cur.fetchone()[0])
        cur.execute('select count(*) from model_versions')
        print('MODEL_VERSIONS', cur.fetchone()[0])
        cur.execute('select count(*) from rules')
        print('RULES', cur.fetchone()[0])
        cur.execute('select count(*) from app_users')
        print('APP_USERS', cur.fetchone()[0])
