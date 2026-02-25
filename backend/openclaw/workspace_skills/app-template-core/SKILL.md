---
name: app-template-core
description: Template namespace for a future application-specific OpenClaw skill. Duplicate this folder, rename it to <your-app>-core, and keep all app-specific logic isolated.
---

# App Template Core Skill

This is a template namespace.

## Required isolation rule

- Rename folder and `name` to your app-specific namespace (example: `finops-core`).
- Keep all endpoints and behaviors inside that app namespace only.
- Never merge another app's endpoints into `strategos-core` or any other existing namespace.

## Placeholder endpoint contract

- `POST /<app>/skills/create_session`
- `POST /<app>/skills/run_engine`
- `GET /<app>/skills/state/{session_id}`

## Auth placeholder

- Header: `Authorization`
- Value: `Bearer ${APP_TEMPLATE_API_TOKEN}`

## Required env placeholders

- `APP_TEMPLATE_API_BASE_URL`
- `APP_TEMPLATE_API_TOKEN`

Before production use, replace all placeholders and validate with:

- `/home/ubuntu/.npm-global/bin/openclaw skills list`
- `/home/ubuntu/.npm-global/bin/openclaw skills check`
