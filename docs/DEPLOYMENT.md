# ReqQuality AI Production Deployment Guide

This guide documents the active production architecture deployed on **Vercel** with **Neon PostgreSQL** and **SMTP** email delivery, plus **Render** documented as an optional backend hosting alternative.

- **Frontend SPA**: Vercel (`https://reqqualityai.site` & `https://www.reqqualityai.site`, Root Directory `frontend`)
- **Backend API (Active)**: Vercel Serverless Python (`https://reqquality-api.vercel.app`, Root Directory `backend`, auto-discovered Flask WSGI entrypoint [`backend/app.py`](../backend/app.py) / [`backend/wsgi.py`](../backend/wsgi.py), health check `/api/health`)
- **Database**: Neon Serverless PostgreSQL (`sslmode=require`)
- **AI Provider**: Server-side Google Gemini (`GEMINI_API_KEY`, `GEMINI_MODEL`, `GEMINI_TIMEOUT_MS`)
- **Email Delivery**: SMTP (`smtplib` with STARTTLS on port `587` or SMTPS on port `465`)

```
Browser (https://reqqualityai.site or https://www.reqqualityai.site)
   │  First-party HTTPS cookies (__Secure-reqquality_access, __Secure-reqquality_refresh)
   ▼
Vercel Frontend (frontend/vercel.json: /api/:path* -> https://reqquality-api.vercel.app/api/:path*)
   │  HTTPS proxy with X-Forwarded-Proto / X-Forwarded-For
   ▼
Vercel Backend API (https://reqquality-api.vercel.app, TRUST_PROXY_HOPS=1)
   ├──► Neon PostgreSQL (pooled runtime URL, sslmode=require, TCP keepalives)
   ├──► Google Gemini API (server-side only, 20s timeout)
   └──► SMTP Provider (invitations + single-use password reset links)
```

> [!IMPORTANT]
> Never commit real database URLs, signing secrets, Gemini API keys, or SMTP passwords to Git. Configure all secrets exclusively inside Vercel Project Settings (or Render if using the optional alternative) and untracked local `.env` files.

---

## 1. Environment Variables

### Active Backend: Vercel (`https://reqquality-api.vercel.app`, Root Directory: `backend`)

Vercel's Python runtime automatically discovers [`backend/app.py`](../backend/app.py) / [`backend/wsgi.py`](../backend/wsgi.py) (`app`) without requiring a separate `backend/vercel.json`.

| Variable | Example / Safe Placeholder | Required | Purpose |
| --- | --- | --- | --- |
| `DATABASE_URL` | `postgresql://<user>:<password>@<ep-pooler>.<region>.aws.neon.tech/neondb?sslmode=require` | Yes | Neon **pooled** PostgreSQL connection string (`-pooler.` host). [`backend/database.py`](../backend/database.py) automatically enforces `sslmode=require` on `.neon.tech` hosts unless `verify-ca`/`verify-full` is specified. |
| `REQQUALITY_SECRET_KEY` | `<64-hex-chars-min-32-bytes>` | Yes | Flask session/HMAC secret (`python -c "import secrets; print(secrets.token_hex(32))"`). Shared across all serverless instances/workers. |
| `JWT_SECRET_KEY` | `<64-hex-chars-min-32-bytes>` | Yes | Independent HS256 signing key for `__Secure-reqquality_access` cookies and CSRF binding. Generate separately from `REQQUALITY_SECRET_KEY`. |
| `GEMINI_API_KEY` | `<your-gemini-api-key>` | Yes | Server-side Google Gemini API key. Never exposed to the browser. |
| `GEMINI_MODEL` | `gemini-3.5-flash-lite` | Yes | Gemini model verified against your API key with `backend/verify_gemini.py`. |
| `GEMINI_TIMEOUT_MS` | `20000` | Yes | Per-request Gemini SDK timeout (`1000`–`25000` ms). |
| `SESSION_COOKIE_SECURE` | `true` | Yes | Production WSGI always enforces HTTPS-only `Secure` cookies (`LOCAL_HTTP_DEVELOPMENT` is `False` outside direct `python app.py` execution). |
| `COOKIE_SAMESITE` | `Lax` | Yes | Keep `Lax` when using the [`frontend/vercel.json`](../frontend/vercel.json) `/api/:path*` same-origin rewrite. Set `None` only if calling `https://reqquality-api.vercel.app` directly cross-origin via `VITE_API_BASE_URL` over HTTPS. |
| `TRUST_PROXY_HOPS` | `1` | Yes | Enables Werkzeug `ProxyFix(x_proto=1, x_for=1)` so Vercel's HTTPS reverse proxy headers populate `request.is_secure` for `426` cookie checks and IP rate limiting. |
| `FRONTEND_ORIGINS` | `https://reqqualityai.site,https://www.reqqualityai.site` | Yes | Comma-separated CORS and write-request `Origin` allowlist (trailing slashes are normalized automatically). |
| `INVITATION_FRONTEND_URL` | `https://reqqualityai.site` | Yes | Base URL embedded into invitation links (`/accept-invitation?token=...`). |
| `PASSWORD_RESET_FRONTEND_URL` | `https://reqqualityai.site` | Recommended | Base URL embedded into password reset links (`/#reset-password?token=...`); defaults to `INVITATION_FRONTEND_URL`. |
| `DB_POOL_MAX_SIZE` | `5` | Optional | Max pooled connections per Python process (keep bounded under Neon connection limits). |
| `DB_POOL_TIMEOUT` | `15` | Optional | Seconds to wait on pool checkout (covers Neon serverless compute wake-up). |
| `DB_CONNECT_TIMEOUT` | `10` | Optional | PostgreSQL TCP/TLS connect timeout in seconds (`3` default if unset). |
| `DB_KEEPALIVES_IDLE` | `30` | Optional | Seconds before libpq sends TCP keepalive probes on idle Neon sockets. |
| `DB_KEEPALIVES_INTERVAL` | `10` | Optional | Seconds between TCP keepalive probes. |
| `DB_KEEPALIVES_COUNT` | `5` | Optional | Failed TCP keepalive probes before dropping a dead socket. |

### Vercel Frontend (`https://reqqualityai.site` & `https://www.reqqualityai.site`, Root Directory: `frontend`)

- **Default setup (same-origin proxy rewrite — active)**:
  - [`frontend/vercel.json`](../frontend/vercel.json) rewrites `/api/:path*` -> `https://reqquality-api.vercel.app/api/:path*` and falls back `/:path*` -> `/index.html` for client routing.
  - Keep `VITE_API_BASE_URL` **unset** in Vercel so all browser API calls target `/api/...` on the active origin (`https://reqqualityai.site`), treating `__Secure-*` auth cookies as **first-party `SameSite=Lax`** cookies.
- **Optional direct cross-origin API mode**:
  - Set `VITE_API_BASE_URL=https://reqquality-api.vercel.app` in Vercel Frontend **Environment Variables**, and set `COOKIE_SAMESITE=None` on the backend.
- **Local Vite development**:
  - Unaffected: [`frontend/vite.config.js`](../frontend/vite.config.js) proxies `/api` to `http://127.0.0.1:5000` on `http://127.0.0.1:5173`.

| Vercel Setting / Variable | Value | Notes |
| --- | --- | --- |
| Root Directory | `frontend` | Contains `package.json`, `vite.config.js`, and `vercel.json`. |
| Framework Preset | `Vite` | Static build output in `frontend/dist`. |
| Build Command | `npm run build` | Uses Vite 6 production build. |
| Output Directory | `dist` | Matches Vite default output. |
| `VITE_API_BASE_URL` | *(unset by default)* | Leave unset when using [`frontend/vercel.json`](../frontend/vercel.json) `/api/:path*` rewrite. |

### Neon PostgreSQL

| Connection Role | Host Pattern | Usage |
| --- | --- | --- |
| Pooled Runtime Connection | `ep-<id>-pooler.<region>.aws.neon.tech/neondb?sslmode=require` | Set as `DATABASE_URL` in Vercel backend env vars for runtime API requests. [`backend/database.py`](../backend/database.py) enforces `sslmode=require` on all `.neon.tech` URLs unless `verify-ca`/`verify-full` is explicitly configured. |
| Direct Connection | `ep-<id>.<region>.aws.neon.tech/neondb?sslmode=require` | Preferred when running one-off local `migrate_sqlite_to_postgres.py`, `pg_dump` backups, or `diagnose_postgres.py` from an authorized workstation. |

> [!NOTE]
> Serverless Vercel deployments require Neon to accept Vercel's outbound connections (disable overly narrow IP Allow rules on the runtime branch, or configure allowlists per Vercel's static IP settings). Outbound port `5432` is required.

### SMTP Email Delivery

| Variable | Example / Safe Placeholder | Purpose |
| --- | --- | --- |
| `SMTP_HOST` | `smtp.example.com` | SMTP relay host (e.g., Resend SMTP, Postmark, SendGrid, Mailgun, or Gmail App Password relay). |
| `SMTP_PORT` | `587` (STARTTLS) or `465` (`SMTP_SSL=true`) | Mail submission port. |
| `SMTP_FROM` | `ReqQuality AI <no-reply@reqqualityai.site>` | Verified sender address matching your domain's SPF/DKIM records. |
| `SMTP_USERNAME` | `<smtp-username>` | Authenticated SMTP username (omit only for unauthenticated internal relays). |
| `SMTP_PASSWORD` | `<smtp-password-or-app-token>` | Required whenever `SMTP_USERNAME` is set. |
| `SMTP_SSL` | `false` | `false` uses STARTTLS with TLS certificate verification; `true` uses implicit `SMTP_SSL` (port `465`). |

---

## 2. Deployment & Verification Checklist

### Step A: Prepare & Verify Neon PostgreSQL
1. Back up any existing Neon branch/database before schema or data operations (`pg_dump` or Neon dashboard branch snapshot).
2. From a workstation with outbound TCP `5432` access, export the **direct** Neon `DATABASE_URL` plus strong `REQQUALITY_SECRET_KEY` and `JWT_SECRET_KEY` temporarily in shell memory, then run read-only diagnostics from `backend/`:
   ```powershell
   .\.venv\Scripts\python.exe diagnose_postgres.py
   ```
   Confirm `parsed: true`, `tls: "certificate and hostname verified"`, and `successful: true` on `SELECT 1`.
3. **(If migrating existing local SQLite data)** Run the explicit repeatable importer from `backend/`:
   ```powershell
   .\.venv\Scripts\python.exe migrate_sqlite_to_postgres.py --sqlite .\instance\reqquality.db
   ```
   Confirm zero errors and expected row counts. Re-running reports `already_present=<N>` cleanly; existing SQLite data is opened read-only.
4. **(If starting with a fresh empty database)** Create the initial Admin account securely via CLI (never expose public admin signup):
   ```powershell
   .\.venv\Scripts\python.exe create_admin.py
   ```
5. Optionally run read-only pooled verification:
   ```powershell
   .\.venv\Scripts\python.exe verify_postgres_readonly.py --output ..\audit\postgres-verify.json
   ```

### Step B: Deploy Backend on Vercel (`https://reqquality-api.vercel.app`)
1. Connect the Vercel API project with Root Directory `backend` (Vercel Python auto-discovers `app` from `app.py` / `wsgi.py`).
2. Populate all required secrets and config variables in Vercel Backend **Environment Variables** (`DATABASE_URL` with Neon `-pooler.` host, `REQQUALITY_SECRET_KEY`, `JWT_SECRET_KEY`, `GEMINI_API_KEY`, `GEMINI_MODEL`, `SMTP_*`).
3. Confirm `TRUST_PROXY_HOPS=1`, `SESSION_COOKIE_SECURE=true`, `COOKIE_SAMESITE=Lax`, `FRONTEND_ORIGINS=https://reqqualityai.site,https://www.reqqualityai.site`, `INVITATION_FRONTEND_URL=https://reqqualityai.site`, and `PASSWORD_RESET_FRONTEND_URL=https://reqqualityai.site`.
4. Redeploy and verify health check + logs:
   - Check Vercel runtime logs for the `startup` log line showing `mode=production_wsgi`, `trust_proxy_hops=1`, `'neon': True`, `'sslmode': 'require'` (with zero credentials/DSNs printed).
   - Verify direct backend health returns HTTP `200`:
     ```sh
     curl -i https://reqquality-api.vercel.app/api/health
     ```
   - Verify Gemini connectivity locally against your production key before testing live AI flows:
     ```sh
     python backend/verify_gemini.py --smoke
     ```

### Step C: Align & Deploy Frontend on Vercel (`https://reqqualityai.site`)
1. Confirm [`frontend/vercel.json`](../frontend/vercel.json) rewrites `/api/:path*` to `https://reqquality-api.vercel.app/api/:path*`.
2. Connect the Vercel Frontend project with Root Directory `frontend`, Framework `Vite`, Build Command `npm run build`, Output Directory `dist`, and `VITE_API_BASE_URL` unset.
3. Confirm proxied health check returns JSON HTTP `200` through the frontend domain:
   ```sh
   curl -i https://reqqualityai.site/api/health
   ```

### Step D: Bare Domain (`reqqualityai.site`) + `www` DNS Setup
1. In your domain DNS provider and Vercel Domains settings:
   - **Apex (`@` / `reqqualityai.site`)**: `A` record (`76.76.21.21` or Vercel-assigned apex `A`/ALIAS target) serving your canonical site (or redirecting to `www` if preferred — keep `FRONTEND_ORIGINS` aligned with whichever canonical host users browse).
   - **`www` (`www.reqqualityai.site`)**: `CNAME` record pointing to `cname.vercel-dns.com` (or Vercel's project-specific CNAME target), added in Vercel Domains.
2. Verify both hostnames resolve, present valid TLS certificates, and serve cleanly:
   ```sh
   curl -I https://reqqualityai.site
   curl -I https://www.reqqualityai.site
   ```
3. Always sign in on your canonical domain (`https://reqqualityai.site`) since host-only `__Secure-reqquality_*` cookies bind strictly to the active host origin.

### Step E: Hosted Login & Core Workflow Verification
1. Open `https://reqqualityai.site/#login` in a clean browser/incognito window.
2. Inspect DevTools Network on sign in (`POST /api/auth/login`):
   - Returns HTTP `200` (not `426`, `403`, or `503`).
   - Response sets `Set-Cookie` for `__Secure-reqquality_access` (`Path=/api/; Secure; HttpOnly; SameSite=Lax`) and `__Secure-reqquality_refresh` (`Path=/api/auth/; Secure; HttpOnly; SameSite=Lax`).
   - No `CORS` or blocked-origin errors in Console.
3. Reload the browser page (`F5`): confirm `GET /api/auth/me` stays authenticated (`200`).
4. Run a CSRF-protected write (e.g., save a test draft or AI analysis) and a PDF download (`Export PDF`), then click **Log out** (`POST /api/auth/logout`) and confirm both cookies are cleared.

### Step F: SMTP Invitation & Password-Reset Email Testing
1. Sign in as Admin (`manager` / `admin`), open **Invitations**, and invite a real test inbox you control (as `Analyst` or `SQA Engineer`).
2. Verify API returns HTTP `201` with `delivery_status: "sent"` (not `502` delivery failed).
3. Open the received email and verify the link targets `https://reqqualityai.site/accept-invitation?token=...` (not `127.0.0.1` or `localhost`), open it, verify the invited email, and set a 12+ character password to activate the account.
4. On `/#login`, click **Forgot password?**, submit the test account email, open the reset email linking to `https://reqqualityai.site/#reset-password?token=...`, complete the reset, and sign in once with the new password.

---

## 3. Optional Alternative: Render Backend (`render.yaml`)

If you decide to move the Flask API off Vercel serverless onto a persistent container host with a 90-second worker timeout (useful for slow Gemini requests and ReportLab cold imports):

1. Import the repository into Render using the root [`render.yaml`](../render.yaml) Blueprint (service `reqquality-ai-api`, `rootDir: backend`, `gunicorn wsgi:app --bind 0.0.0.0:$PORT --workers 2 --threads 4 --timeout 90`, `healthCheckPath: /api/health`).
2. Populate the `sync: false` secrets in Render (`DATABASE_URL`, `REQQUALITY_SECRET_KEY`, `JWT_SECRET_KEY`, `GEMINI_API_KEY`, `SMTP_*`) and ensure `TRUST_PROXY_HOPS=1` and `FRONTEND_ORIGINS=https://reqqualityai.site,https://www.reqqualityai.site`.
3. Update [`frontend/vercel.json`](../frontend/vercel.json) `/api/:path*` destination to your Render service URL (`https://<your-render-service>.onrender.com/api/:path*`) and redeploy Vercel Frontend.
