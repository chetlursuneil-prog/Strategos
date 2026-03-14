set -e
cd ~/strategos-backend
source .venv/bin/activate
alembic -c alembic.ini upgrade head
systemctl --user restart strategos-backend
sleep 2
systemctl --user --no-pager status strategos-backend | sed -n '1,60p'
echo ---
curl -sS -i http://127.0.0.1:8000/api/v1/auth/me | sed -n '1,20p'