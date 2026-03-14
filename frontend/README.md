# STRATEGOS Frontend

This is the Next.js App Router frontend for Strategos.

## What lives here

- Public site: `app/page.tsx`
- Auth pages:
  - `app/login/page.tsx`
  - `app/verify-email/page.tsx`
  - `app/forgot-password/page.tsx`
  - `app/reset-password/page.tsx`
- Main product dashboard: `app/dashboard/*`
- Workspace advisor UI: `app/dashboard/workspace/page.tsx`
- Session replay/detail UI: `app/dashboard/sessions/[id]/page.tsx`
- Access approvals (admin): `app/dashboard/access/page.tsx`
- Shared API client: `lib/api.ts`
- Auth context/token handling: `lib/auth.tsx`

## Runtime dependencies

- Next.js (App Router)
- React
- TypeScript
- TailwindCSS

## Environment

Set frontend API base URL:

```bash
NEXT_PUBLIC_API_BASE=http://localhost:8000/api/v1
```

## Run locally

```powershell
cd frontend
npm install
npm run dev
```

Then open `http://localhost:3000`.

## Notes

- Frontend expects backend auth and intake/advisory/report endpoints to be available.
- Full architecture and end-to-end flow are documented in the root `README.md`.
