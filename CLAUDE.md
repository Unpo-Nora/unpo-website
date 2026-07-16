# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Unified platform for the **UNPO** (B2B wholesale) and **NORA** (B2C) brands: a public marketing/catalog site plus a staff-only admin portal that doubles as a CRM (leads), inventory, sales, purchasing, finance, and HR system. Two services — a Next.js frontend (`frontend/`) and a FastAPI backend (`backend/`) — backed by PostgreSQL.

Historically the codebase treats NORA as a B2C sub-brand of UNPO (shared frontend, shared backend, shared DB). **That is the legacy state, not the target** — see the business rules below before doing any UNPO/NORA work.

## Business rules: UNPO / NORA separation

These rules govern the in-progress split of NORA out from UNPO. They take precedence over the "unified platform" framing above whenever the two conflict.

**Target model**
- NORA is **no longer a sub-brand of UNPO**. Treat it as its own, fully separate brand — not a B2C wing of UNPO.
- NORA gets its **own CRM** and its **own customer-facing public website**, each on its **own separate domain** (the NORA public web and the NORA CRM are on different domains from each other and from UNPO).
- NORA has its **own dedicated seller**, WhatsApp **1131488378**. UNPO leads/sales must not route to this number, and NORA leads/sales must not route to UNPO sellers.
- Do **not** mix branding, routes, leads, clients, catalogs, WhatsApp messages, or commercial logic between UNPO and NORA without a prior diagnosis.

**How to make changes (process is mandatory)**
- Every separation change ships **in stages**: (1) diagnosis, (2) technical plan, (3) minimal implementation, (4) validation. Do not jump straight to implementation.
- **Before** implementing any separation change, first identify what is currently **shared**: shared files, shared components, shared endpoints, and shared models/tables. Surface that inventory as part of the diagnosis.
- Do **not delete or remove UNPO code** while building NORA — only with explicit approval.
- Do **not touch production, environment variables, Alembic migrations, or the `/fix_*` / `/migrate_*` endpoints** without explicit approval.

## Running the project

The intended way to run everything (db + backend + frontend + Adminer) is Docker Compose from the repo root:

```bash
docker-compose up -d --build
```

- Public web: http://localhost:3000 · Admin/CRM: http://localhost:3000/admin/login
- API + Swagger docs: http://localhost:8000/docs
- Adminer (DB GUI): http://localhost:8081 (db `unpo_nora_db`, user `unpo_admin`)

Both containers mount their source as volumes with hot-reload (`uvicorn --reload`, `next dev`), so most code changes need no rebuild — only dependency changes (`requirements.txt` / `package.json`) require `--build`.

### Running services individually

Frontend (`cd frontend`): `npm run dev` · `npm run build` · `npm start` · `npm run lint` (ESLint via `eslint-config-next`). There is no frontend test suite.

Backend (`cd backend`): `uvicorn app.main:app --reload --port 8000`. Requires a reachable Postgres (`DATABASE_URL`). There is no automated test suite — the many `check_*.py`, `tmp_*.py`, and root-level `*.py` scripts are one-off DB inspection/maintenance utilities, not tests.

## Architecture

### Backend (FastAPI + SQLAlchemy)

- `app/main.py` — app entry: registers FastAPI, routers, CORS middleware, exception handlers, static mounts and the `/health` check. **The startup runs NO DDL**: it does **not** call `Base.metadata.create_all()`, and it does **not** auto-run `alembic upgrade` / `stamp` / `downgrade`. **Alembic is the single authorized mechanism for creating and evolving the PostgreSQL schema** — the active baseline is `71e9e987f7d2` (in `backend/alembic/versions/`, `down_revision=None`, scoped to `public`). On an **empty** database the schema is created explicitly with `alembic upgrade head`; an existing DB adopts a revision via `alembic stamp` (see `docs/unpo-alembic-baseline-runbook.md`). The historical one-off maintenance scripts (`backend/upgrade_db.py`, `backend/migrate_*.py`, `backend/scripts/maintenance/*`) and the archived migrations in `backend/alembic/legacy_versions/` are **legacy** and must **not** be used as a pattern for new migrations.
- `app/models.py` — the single source of truth for the data model (~25 SQLAlchemy tables). Core domains: `Product`/`Category`/`Brand`, `Lead` (CRM, with `LeadStatus` and seller assignment), `SaleOrder`/`OrderItem`, `Purchase`/`Supplier`/`PurchaseItem`, `FinancialTransaction`/`Expense`/`CapitalIva` (finance, with Spanish field names like `tipo_movimiento`, `monto`), `User`, `Employee`, `PageView`, `InventoryAuditLog`. Many enums are defined here too.
- `app/routers/*.py` — one router per domain (`products`, `leads`, `auth`, `analytics`, `sales`, `settings`, `users`, `hr`, `finance`). All are registered in `main.py`.
- `app/crud.py` — DB access helpers shared by routers. `app/schemas.py` / `app/schemas_auth.py` — Pydantic request/response models.
- `app/meta_api.py` — Meta (Facebook/Instagram) integration for lead ingestion. `app/utils/` — `auth.py` (JWT + bcrypt), `importer.py` / `product_importer.py` (Excel/CSV import from `backend/data/`), `pdf_generator.py` (budget/order PDFs via reportlab).
- Product images/videos are served by the backend from `backend/data/images` and `backend/data/videos` under `/static/images` and `/static/videos`.

### Auth & roles

JWT bearer tokens. `auth.get_current_user` (in `routers/auth.py`) decodes the token; the `sub` claim is the user **email**. **There is no role-based dependency** — endpoints that need authorization re-check `current_user.role` inline (e.g. `if current_user.role != "admin": raise HTTPException(...)`). The two roles are `"admin"` and `"vendedor"` (seller); follow the existing inline-check pattern when gating new endpoints. Staff tokens last 12h (`ACCESS_TOKEN_EXPIRE_MINUTES_STAFF`), others 30m.

### Frontend (Next.js 14 App Router)

- Route groups separate the brands/areas: `app/(unpo)/` (UNPO public + catalog), `app/(nora)/nora/` (NORA public), and `app/admin/` (the staff portal — sales, inventory, clients, analytics, hr, purchases, users, import, login). `app/admin/layout.tsx` wraps the portal.
- `context/AuthContext.tsx` — `AuthProvider` / `useAuth`. The JWT is stored in `localStorage` under `token`; on mount it validates against `/auth/me`. After login both roles are routed to `/admin/sales`.
- Each admin screen is a thin `page.tsx` that renders a big stateful component from `components/dashboard/` (e.g. `SellerDashboard`, `InventoryDashboard`, `AnalyticsDashboard`, `CloseSaleModal`). These dashboards hold most of the business logic and call the API directly.
- **API calls go straight to the backend**, not through a Next API layer. The near-universal pattern is:
  ```ts
  fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/<path>`, {
    headers: { Authorization: `Bearer ${localStorage.getItem('token')}` }
  })
  ```
  Reuse this exact pattern (including the localhost fallback) for new calls. Note: `next.config.mjs` defines an `/api/*` → `BACKEND_URL` rewrite, but the app does not use it in practice — don't rely on it.
- UI: Tailwind CSS, `lucide-react` icons, `recharts` for analytics charts, `xlsx` for spreadsheet import/export, `jspdf`/`html2canvas` for client-side PDF/budget generation (`utils/generateBudgetPdf.ts`).

## Configuration gotchas

- Backend config is all env-driven with insecure dev defaults baked into source: `DATABASE_URL`, `SECRET_KEY`, `ALGORITHM`, `CORS_ORIGINS` (comma-separated; falls back to a hardcoded prod allowlist in `main.py`). Override these in `.env` / the deployment env for real environments.
- The frontend reads `NEXT_PUBLIC_API_URL` at build/run time. `frontend/.env.production` contains stale `VITE_*` keys from a previous Vite setup — they are **not** used by Next.js; ignore them.
- `docker-compose.yml` injects `BACKEND_URL` into the frontend (for the unused rewrite), while the actual client code reads `NEXT_PUBLIC_API_URL` — be aware these are two different variables.

## Conventions

- The product domain keys on **SKU** (string) as much as on numeric id (see `crud.get_product(db, sku=...)`).
- Finance/purchasing models and fields are in **Spanish** (`monto`, `fecha`, `tipo_movimiento`, `EGRESO`/`INGRESO`); product/lead/sales models are mostly English. Match whichever domain you're editing.
- User-facing strings (API error `detail`, UI copy) are in Spanish.

## Language

- Respond to the user **in Spanish** (Rioplatense / neutral).
- Keep technical names, commands, paths, variables, error messages, and code in **English** where that is their natural form — do not translate identifiers or CLI output.
- If the user pastes logs or errors in English, explain them in Spanish (the explanation is in Spanish; quote the original English text as-is).
- Commit messages may be written in Spanish unless the project indicates otherwise.
