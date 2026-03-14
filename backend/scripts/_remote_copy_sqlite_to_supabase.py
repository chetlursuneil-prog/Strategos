import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
import psycopg

SQLITE_PATH = Path('/home/ubuntu/strategos-backend/strategos_dev.db')
ENV_PATH = Path('/home/ubuntu/.config/strategos/strategos.env')

for line in ENV_PATH.read_text().splitlines():
    s=line.strip()
    if not s or s.startswith('#') or '=' not in s:
        continue
    k,v=s.split('=',1)
    os.environ[k]=v

pg_url = os.environ['DATABASE_URL']
now = datetime.now(timezone.utc)

TABLES_ORDER = [
    'tenants','model_versions','metrics','coefficients','rules','rule_conditions','rule_impacts',
    'state_definitions','state_thresholds','restructuring_templates','restructuring_rules',
    'transformation_sessions','transformation_scenarios','audit_logs','app_users','auth_tokens'
]

scon = sqlite3.connect(str(SQLITE_PATH))
scon.row_factory = sqlite3.Row
scur = scon.cursor()

with psycopg.connect(pg_url, prepare_threshold=0) as pcon:
    with pcon.cursor() as pcur:
        pcur.execute('TRUNCATE TABLE ' + ', '.join(TABLES_ORDER) + ' RESTART IDENTITY CASCADE', prepare=False)

        existing_mv_ids = set()

        def ensure_model_version(model_version_id: str, tenant_id: str):
            if model_version_id in existing_mv_ids:
                return
            pcur.execute(
                """
                INSERT INTO model_versions (id, tenant_id, name, description, created_at, updated_at, is_active)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO NOTHING
                """,
                (
                    model_version_id,
                    tenant_id,
                    f"Imported Legacy {model_version_id[:8]}",
                    "Auto-created during SQLite -> Supabase migration to preserve historical sessions.",
                    now,
                    now,
                    False,
                ),
                prepare=False,
            )
            existing_mv_ids.add(model_version_id)

        for table in TABLES_ORDER:
            scur.execute(f'PRAGMA table_info({table})')
            cols_info = scur.fetchall()
            cols = [r['name'] for r in cols_info]
            if not cols:
                print(table, 'SKIP_NO_COLUMNS')
                continue

            scur.execute(f'SELECT {", ".join(cols)} FROM {table}')
            rows = scur.fetchall()
            if not rows:
                print(table, 0)
                continue

            placeholders = ', '.join(['%s'] * len(cols))
            insert_sql = f'INSERT INTO {table} ({", ".join(cols)}) VALUES ({placeholders})'

            inserted = 0
            skipped = 0
            for r in rows:
                vals = []
                bad = False
                row_map = {}
                for idx, c in enumerate(cols):
                    val = r[c]
                    ctype = (cols_info[idx]['type'] or '').upper()
                    if val is None:
                        row_map[c] = None
                        vals.append(None)
                        continue
                    if 'UUID' in ctype:
                        try:
                            norm = str(uuid.UUID(str(val)))
                            row_map[c] = norm
                            vals.append(norm)
                        except Exception:
                            bad = True
                            break
                    elif 'BOOL' in ctype:
                        row_map[c] = bool(val)
                        vals.append(bool(val))
                    else:
                        row_map[c] = val
                        vals.append(val)
                if bad:
                    skipped += 1
                    continue

                if table == 'model_versions':
                    mv_id = row_map.get('id')
                    if mv_id:
                        existing_mv_ids.add(mv_id)

                if table == 'transformation_sessions':
                    mv_id = row_map.get('model_version_id')
                    tenant_id = row_map.get('tenant_id')
                    if mv_id and tenant_id:
                        ensure_model_version(mv_id, tenant_id)

                pcur.execute(insert_sql, tuple(vals), prepare=False)
                inserted += 1
            print(table, inserted, 'skipped', skipped)

    pcon.commit()

print('MIGRATION_DONE')
