# OpenClaw Workspace Skills (Namespaced)

This directory contains skill folders intended to be copied into OpenClaw workspace skills:

- EC2 target root: `~/.openclaw/workspace/skills/`
- STRATEGOS namespace: `~/.openclaw/workspace/skills/strategos-core/`
- Future app scaffold: `app-template-core/` (copy + rename per app)

## Why this structure

To prevent cross-application mixing, each application must own a unique top-level skill folder.

Examples:

- STRATEGOS: `strategos-core`
- Future app (example): `finops-core`
- Future app (example): `supplychain-core`

## Rule

Never place one app's files inside another app's skill folder.
Each app must have its own isolated namespace folder under `workspace/skills`.

## Quick start for a new app

1. Copy `app-template-core` to a new folder, for example `finops-core`.
2. Update `SKILL.md` frontmatter `name` and endpoint/auth placeholders.
3. Keep any contract JSON inside the same namespace folder.
4. Deploy only that new namespace to EC2; do not modify `strategos-core`.
