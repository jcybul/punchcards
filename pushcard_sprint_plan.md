# Pushcard Project — Sprint Plan

## Milestone 0 — Housekeeping (project sanity)

### T0.1 ENV + Secrets inventory
**Goal:** Everything runs locally with correct envs.
- **Tasks**
  - Create `/ops/.env.example` for **backend** (Flask):
    - `DATABASE_URL`, `SUPABASE_JWT_SECRET`, `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`
    - `APPLE_TEAM_ID`, `PASS_TYPE_ID`, `WALLET_CERTS_DIR`, `PASS_P12_PASSWORD`
  - Create `/apps/frontend/.env.local.example` for **Next.js**:
    - `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`
    - `NEXT_PUBLIC_API_URL` (your Flask base URL)
- **DoD**
  - `cp .env.example .env` works in both apps and both apps boot locally.

### T0.2 Dev data seed
**Goal:** You can recreate a dev DB quickly.
- **Tasks**
  - Update `scripts/seed.py` for: 1 merchant, 1 program, 1 staff mapping (your auth.user id).
  - Add `make dev-seed` command in README.
- **DoD**
  - Running the seed creates consistent records and prints IDs.

---

## Milestone 1 — Backend API Hardening (Auth + CRUD)

### T1.1 JWT verification middleware
**Goal:** All protected routes use the same check.
- **Tasks**
  - Ensure `auth_service.py`’s `require_auth` is applied to protected blueprints.
  - Add `/healthz` (public) and `/me` (protected) endpoints.
- **DoD**
  - `/me` returns `{ user_id }` when called with Supabase access token; 401 otherwise.

### T1.2 Role model + checks (minimal)
**Goal:** You can authorize staff actions.
- **Tasks**
  - Confirm `profiles` and `merchant_users` tables exist (Alembic up to head).
  - Add helper: `require_card_owner_or_merchant_staff(card_id)`.
- **DoD**
  - Punch endpoint denies non-staff; allows staff/owner; owner of the card can read.

### T1.3 Programs CRUD (admin-you only)
**Goal:** You can create/manage punch programs via API.
- **Tasks**
  - `POST /programs` (name, punches_required, merchant_id).
  - `GET /programs/:id` (+ basic list `GET /programs?merchant_id`).
  - Restrict POST/PATCH to platform admin (via profiles.platform_role='admin').
- **DoD**
  - Postman calls pass and program appears in DB.

---

## Milestone 2 — Join Flow & Cards

### T2.1 QR join endpoint
**Goal:** Users scan QR → get/create their WalletCard.
- **Tasks**
  - `GET /programs/:program_id/join` (requires auth): find-or-create `(user_id, program_id)`; return `{ card_id, program }`.
  - Enforce uniqueness with `uq_wallet_cards_user_program`.
- **DoD**
  - Calling with a valid token returns same `card_id` on repeated calls.

### T2.2 Cards read endpoints
**Goal:** Users see their cards; staff can view any card for their merchant.
- **Tasks**
  - `GET /cards/mine` (list current user’s cards with program summary).
  - `GET /cards/:id` (owner or merchant staff).
- **DoD**
  - Owner sees their card; staff sees card detail; others 403.

### T2.3 Punch + redeem (server logic only)
**Goal:** Update counts; record history.
- **Tasks**
  - `POST /cards/:id/punch` (staff only) `{ amount: 1, source: "qr" }`
    - Increment `current_punches`, roll into `reward_credits` when reaching `punches_required`.
    - Insert a `punches` row.
    - **Increment `update_tag`** on `wallet_cards`.
  - `POST /cards/:id/redeem` (staff only) `{ credits: 1 }`
    - Decrement `reward_credits` >= 1.
    - Insert a `redemptions` row.
    - **Increment `update_tag`**.
- **DoD**
  - DB reflects updates; negative balances impossible; errors handled.

---

## Milestone 3 — Apple Wallet Basics (static issuance)

### T3.1 Pass builder module
**Goal:** Reuse your working signing code as a service.
- **Tasks**
  - Create `app/apple_passes.py` with:
    - `build_pass_json(card, program, merchant, options)` → dict
    - `build_pkpass(pass_json)` → bytes (signed ZIP)
  - Load assets from `assets/` (icon/logo), load certs from `WALLET_CERTS_DIR`.
- **DoD**
  - Unit-test function generates bytes and has correct content-type.

### T3.2 Issuance endpoint (download)
**Goal:** Serve `.pkpass` per card.
- **Tasks**
  - `GET /passes/:card_id.pkpass` (owner only or staff) → returns pkpass bytes.
  - Include in `pass.json` at least:
    - `passTypeIdentifier`, `teamIdentifier`, `serialNumber = card.id`
    - `webServiceURL` (point to your API; even if stubbed)
    - `authenticationToken = card.auth_token`
    - Fields showing punches/required/credits
- **DoD**
  - Installing pass reflects current counts at time of download.

---

## Milestone 4 — PassKit Web Service (live updates)

### T4.1 Minimal web service endpoints (Apple spec)
**Goal:** Implement the required endpoints in your Flask app.
- **Tasks**
  - `GET /v1/passes/{passTypeIdentifier}/{serialNumber}`
  - `GET /v1/devices/{deviceLibraryIdentifier}/registrations/{passTypeIdentifier}/{serialNumber}`
  - `POST /v1/devices/{deviceLibraryIdentifier}/registrations/{passTypeIdentifier}/{serialNumber}`
  - `DELETE /v1/devices/{deviceLibraryIdentifier}/registrations/{passTypeIdentifier}/{serialNumber}`
  - `GET /v1/serialNumbers/{deviceLibraryIdentifier}?passesUpdatedSince=<tag>`
- **DoD**
  - Apple can register your device and query for updates without errors.

### T4.2 Update lifecycle
**Goal:** Card changes notify Wallet that there’s a new version.
- **Tasks**
  - In punch/redeem, after DB commit, **bump `update_tag`**.
  - Implement a tiny **“dirty card”** table or just rely on `update_tag`.
- **DoD**
  - Opening the pass after a punch shows the updated count (refresh within Wallet or after some seconds).

---

## Milestone 5 — Frontend MVP (Next.js)

### T5.1 Auth pages
- Signup form: email, password, first name, last name, birthdate.
- On signup or first login: `upsert` into `profiles`.

### T5.2 “Join program” page
- `/join/[programId]` route: call join endpoint, show “Add to Apple Wallet”.

### T5.3 “My cards” page
- `/cards` route: list user cards, re-download pass.

---

## Milestone 6 — Staff Console (basic)

### T6.1 Staff punch screen
- `/staff/punch?card=<id>` with punch button.

### T6.2 Staff redeem screen
- `/staff/redeem?card=<id>` with redeem button.

---

## Milestone 7 — Deployment & Ops

- Deploy backend (Render/Railway/Fly.io).
- Deploy frontend (Vercel).
- Configure CORS + custom domains.
- Run full iOS test flow.

---

## Milestone 8 — Nice-to-haves / Next Sprint
- APNs push notifications.
- Google Wallet support.
- Merchant dashboards.
- Audit logs + metrics.
- Background jobs for cleanup.

---

## Backlog Tickets

- [ ] Add `/healthz` endpoint.
- [ ] Add `/me` endpoint and test JWT verification.
- [ ] Programs: POST/GET/PATCH + admin gate.
- [ ] Join: `GET /programs/:id/join`.
- [ ] Cards: `GET /cards/mine`, `GET /cards/:id`.
- [ ] Punch: `POST /cards/:id/punch`, bump `update_tag`.
- [ ] Redeem: `POST /cards/:id/redeem`, bump `update_tag`.
- [ ] History: `GET /cards/:id/history`.
- [ ] Pass builder module (`build_pass_json`, `build_pkpass`).
- [ ] Issue route: `GET /passes/:card_id.pkpass`.
- [ ] PassKit WS: device registration endpoints.
- [ ] PassKit WS: pass query + serials since updateTag.
- [ ] Next.js: signup/login pages + profile upsert.
- [ ] Next.js: `/join/[programId]` flow.
- [ ] Next.js: `/cards` page.
- [ ] Next.js: staff punch/redeem pages.
- [ ] Deploy backend + CORS.
- [ ] Deploy frontend + custom domain.
- [ ] End-to-end test checklist on iPhone.
