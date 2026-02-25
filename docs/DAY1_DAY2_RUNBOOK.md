# STRATEGOS Day 1 / Day 2 Execution Runbook

This runbook is for your target architecture:
- OpenClaw/Sara on EC2-A
- STRATEGOS backend on EC2-B (separate instance)

The two services remain separate and communicate via HTTPS/HTTP API.

---

## Day 1 — Git First (Complete)

### 1) Initialize local git repository

```powershell
git init
```

### 2) Verify ignore rules include secrets/runtime artifacts

- Root `.gitignore` should include:
  - `.env`, `.env.local`, `backend/.env`, `frontend/.env.local`
  - `.venv/`, `node_modules/`, `frontend/.next/`
  - `*.log`, `*.pid`, caches

### 3) Create and push GitHub repository

```powershell
# from workspace root
git add .
git commit -m "chore: day1 baseline and deployment runbook"
git branch -M main
git remote add origin <YOUR_GITHUB_REPO_URL>
git push -u origin main
```

### 4) Add GitHub secrets (for CI/CD later)

Recommended initial secrets:
- `EC2_HOST_STRATEGOS`
- `EC2_USER_STRATEGOS`
- `EC2_SSH_KEY_STRATEGOS`
- `DATABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `SECRET_KEY`

---

## Day 2 — New STRATEGOS EC2 Deployment

### Inputs you need

- EC2-B public IP/DNS
- SSH key path for EC2-B
- PostgreSQL/Supabase `DATABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `SECRET_KEY`

### 1) Deploy backend files to EC2-B

Use `backend/scripts/deploy_strategos_ec2.ps1`:

```powershell
cd backend
.\scripts\deploy_strategos_ec2.ps1 `
  -RemoteHost <EC2_B_IP_OR_DNS> `
  -KeyPath <PATH_TO_PEM> `
  -DatabaseUrl "<DATABASE_URL>" `
  -SupabaseServiceRoleKey "<SUPABASE_SERVICE_ROLE_KEY>" `
  -SecretKey "<SECRET_KEY>"
```

This script:
- Uploads STRATEGOS backend to `~/strategos-backend`
- Creates Python venv
- Installs requirements
- Writes `~/.config/strategos/strategos.env`
- Runs migrations
- Seeds deterministic baseline
- Installs/starts `strategos-backend.service` (systemd)

### 2) Validate STRATEGOS API on EC2-B

```bash
curl -i http://127.0.0.1:8000/api/v1/health
curl -i http://127.0.0.1:8000/api/v1/admin/agents
```

### 3) Point OpenClaw (EC2-A) to STRATEGOS EC2-B

Set on EC2-A runtime env (where OpenClaw runs):

```bash
export STRATEGOS_API_BASE_URL="http://<EC2_B_PRIVATE_IP_OR_DNS>:8000/api/v1"
export STRATEGOS_API_TOKEN=""
```

Then restart OpenClaw gateway:

```bash
/home/ubuntu/.npm-global/bin/openclaw gateway restart
```

### 4) End-to-end verification (Sara + webapp)

- Sara/OpenClaw test: STRATEGOS strict advisory prompt returns final payload keys.
- Webapp test: `/advisory/skills/board_insights/{session_id}` returns non-empty insights.

---

## Important Notes

- You do **not** need a third instance for this stage.
- This keeps architectural separation while minimizing cost.
- Keep Sara app-agnostic; STRATEGOS remains one capability namespace.

---

## Stop Point

After Day 2 passes, pause for approval before Day 3 (public domain + TLS + production ingress).