# ReqQuality AI Production Deployment Guide

This guide documents the production architecture aligned with the FYP stack:

- **Frontend SPA**: Vercel (`https://www.reqqualityai.site`, with apex `https://reqqualityai.site` redirecting canonically to `www`)
- **Backend API**: Render Python Web Service running Gunicorn (`backend/wsgi.py` -> `wsgi:app`, `90s` worker timeout, health check `/api/health`)
- **Database**: Neon Serverless PostgreSQL (`sslmode=require`)
- **AI Provider**: Server-side Google Gemini (`GEMINI_API_KEY`, `GEMINI_MODEL`, `GEMINI_TIMEOUT_MS`)
- **Email Delivery**: SMTP (`smtplib` with STARTTLS on port `587` or SMTPS on port `465`)

```
Browser (https://www.reqqualityai.site)
   │  First-party HTTPS cookies (__Secure-reqquality_access, __Secure-reqquality_refresh)
   ▼
Vercel Edge (frontend/vercel.json: /api/:path* -> Render URL)
   │  HTTPS proxy with X-Forwarded-Proto / X-Forwarded-For
   ▼
Render Web Service (render.yaml: gunicorn wsgi:app --timeout 90, TRUST_PROXY_HOPS=1)
   ├──► Neon PostgreSQL (pooled runtime URL, sslmode=require, TCP keepalives)
   ├──► Google Gemini API (server-side only, 20s timeout)
   └──► SMTP Provider (invitations + single-use password reset links)
```

> [!IMPORTANT]
> Never commit real database URLs, signing secrets, Gemini API keys, or SMTP passwords to Git. Set all sensitive values strictly in Render, Vercel, or local untracked `.env` files.

---

## 1. Environment Variables

### Render Backend (`render.yaml` / Render Dashboard)

`render.yaml` configures non-secret defaults and marks secrets as `sync: false` so Render prompts for them securely during Blueprint import.

| Variable | Example / Safe Placeholder | Required | Purpose |
| --- | --- | --- | --- |
| `PYTHON_VERSION` | `3.12.8` | Yes | Python runtime version on Render. |
| `DATABASE_URL` | `postgresql://<user>:<password>@<ep-pooler>.<region>.aws.neon.tech/neondb?sslmode=require` | Yes | Neon **pooled** PostgreSQL connection string (`-pooler.` host). Render/backend enforces `sslmode=require` for `.neon.tech` hosts. |
| `REQQUALITY_SECRET_KEY` | `<64-hex-chars-min-32-bytes>` | Yes | Flask session/HMAC secret (`python -c "import secrets; print(secrets.token_hex(32))"`). Shared across all Gunicorn workers. |
| `JWT_SECRET_KEY` | `<64-hex-chars-min-32-bytes>` | Yes | Independent HS256 signing key for `__Secure-reqquality_access` cookies and CSRF binding. Generate separately from `REQQUALITY_SECRET_KEY`. |
| `GEMINI_API_KEY` | `<your-gemini-api-key>` | Yes | Server-side Google Gemini API key. Never exposed to the browser. |
| `GEMINI_MODEL` | `gemini-3.5-flash-lite` | Yes | Gemini model verified against your API key with `backend/verify_gemini.py`. |
| `GEMINI_TIMEOUT_MS` | `20000` | Yes | Per-request Gemini SDK timeout (`1000`–`25000` ms). Render Gunicorn uses `--timeout 90` so AI calls and ReportLab PDF exports never hit worker timeouts. |
| `SESSION_COOKIE_SECURE` | `true` | Yes | Production WSGI always enforces HTTPS-only `Secure` cookies (`LOCAL_HTTP_DEVELOPMENT` is `False` under `wsgi:app`). |
| `COOKIE_SAMESITE` | `Lax` | Yes | Keep `Lax` when using the Vercel `/api/:path*` same-origin rewrite. Set `None` only if calling Render directly cross-origin from `VITE_API_BASE_URL` over HTTPS. |
| `TRUST_PROXY_HOPS` | `1` | Yes | Enables Werkzeug `ProxyFix(x_proto=1, x_for=1)` so Render's TLS reverse proxy headers mark requests as `https://` for `426` cookie checks and IP rate limiting. |
| `FRONTEND_ORIGINS` | `https://www.reqqualityai.site,https://reqqualityai.site` | Yes | Comma-separated CORS and write-request `Origin` allowlist (trailing slashes are ignored automatically). |
| `INVITATION_FRONTEND_URL` | `https://www.reqqualityai.site` | Yes | Base URL embedded into invitation links (`/accept-invitation?token=...`). |
| `PASSWORD_RESET_FRONTEND_URL` | `https://www.reqqualityai.site` | Recommended | Base URL embedded into password reset links (`/#reset-password?token=...`); defaults to `INVITATION_FRONTEND_URL`. |
| `DB_POOL_MAX_SIZE` | `5` | Optional | Max pooled connections per Gunicorn worker (keep bounded under Neon connection limits). |
| `DB_POOL_TIMEOUT` | `15` | Optional | Seconds to wait on pool checkout (covers Neon serverless compute wake-up). |
| `DB_CONNECT_TIMEOUT` | `10` | Optional | PostgreSQL TCP/TLS connect timeout in seconds (default `3` locally, `10` in `render.yaml`). |
| `DB_KEEPALIVES_IDLE` | `30` | Optional | Seconds before libpq sends TCP keepalive probes on idle Neon sockets. |
| `DB_KEEPALIVES_INTERVAL` | `10` | Optional | Seconds between TCP keepalive probes. |
| `DB_KEEPALIVES_COUNT` | `5` | Optional | Failed TCP keepalive probes before dropping a dead socket. |

### Vercel Frontend (`frontend/vercel.json`)

- **Recommended setup (same-origin proxy rewrite — default)**:
  - Keep `frontend/vercel.json` pointing `/api/:path*` to your Render service URL (`https://<your-render-service>.onrender.com/api/:path*`).
  - Keep `VITE_API_BASE_URL` **unset** in Vercel so all browser API calls target `/api/...` on `https://www.reqqualityai.site`, treating `__Secure-*` auth cookies as **first-party `SameSite=Lax`** cookies (avoiding third-party cookie blocking in Safari/Chrome/Firefox).
- **Optional direct cross-origin API mode**:
  - Set `VITE_API_BASE_URL=https://<your-render-service>.onrender.com` in Vercel **Build & Environment Variables**, and set `COOKIE_SAMESITE=None` on Render.
- **Local Vite development**:
  - Unaffected: `frontend/vite.config.js` continues proxying `/api` to `http://127.0.0.1:5000` on `http://127.0.0.1:5173`.

| Vercel Setting / Variable | Value | Notes |
| --- | --- | --- |
| Root Directory | `frontend` | Contains `package.json`, `vite.config.js`, and `vercel.json`. |
| Framework Preset | `Vite` | Static build output in `frontend/dist`. |
| Build Command | `npm run build` | Uses Vite 6 production build. |
| Output Directory | `dist` | Matches Vite default output. |
| `VITE_API_BASE_URL` | *(unset by default)* | Leave unset when using `frontend/vercel.json` `/api/:path*` rewrite. |

### Neon PostgreSQL

| Connection Role | Host Pattern | Usage |
| --- | --- | --- |
| Pooled Runtime Connection | `ep-<id>-pooler.<region>.aws.neon.tech/neondb?sslmode=require` | Set as `DATABASE_URL` in Render for runtime application requests. `backend/database.py` enforces `sslmode=require` on all `.neon.tech` URLs unless `verify-ca`/`verify-full` is explicitly configured. |
| Direct Connection | `ep-<id>.<region>.aws.neon.tech/neondb?sslmode=require` | Preferred when running one-off local `migrate_sqlite_to_postgres.py`, `pg_dump` backups, or `diagnose_postgres.py` from an authorized workstation. |

> [!NOTE]
> If Neon IP Allow is enabled on your branch, allowlist Render's outbound egress IPs (paid/static or region egress) or disable restrictive IP allowlists before testing hosted login. Port `5432` outbound access is required.

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

### Step B: Deploy Backend on Render
1. Import the repository into Render using the root [`render.yaml`](../render.yaml) Blueprint (service `reqquality-ai-api`, `rootDir: backend`).
2. Populate all `sync: false` environment variables in Render (`DATABASE_URL` with Neon `-pooler.` host, `REQQUALITY_SECRET_KEY`, `JWT_SECRET_KEY`, `GEMINI_API_KEY`, `SMTP_*`).
3. Confirm `TRUST_PROXY_HOPS=1`, `SESSION_COOKIE_SECURE=true`, `COOKIE_SAMESITE=Lax`, and `FRONTEND_ORIGINS=https://www.reqqualityai.site,https://reqqualityai.site`.
4. After Render builds and starts Gunicorn:
   - Check Render logs for the `startup` log line showing `mode=production_wsgi`, `trust_proxy_hops=1`, `'neon': True`, `'sslmode': 'require'` (with zero credentials/DSNs printed).
   - Verify health endpoint returns HTTP `200`:
     ```sh
     curl -i https://<your-render-service>.onrender.com/api/health
     ```
   - Run Gemini connectivity verification inside a one-off Render shell or with your production key:
     ```sh
     python backend/verify_gemini.py --smoke
     ```

### Step C: Align & Deploy Frontend on Vercel
1. Ensure [`frontend/vercel.json`](../frontend/vercel.json) rewrites `/api/:path*` to the live Render service URL (`https://<your-render-service>.onrender.com/api/:path*`). If your Render URL differs from `https://reqquality-ai-api.onrender.com`, update [`frontend/vercel.json`](../frontend/vercel.json) and redeploy.
2. Connect the repository to Vercel with Root Directory `frontend`, Framework `Vite`, Build Command `npm run build`, Output Directory `dist`.
3. Confirm `https://www.reqqualityai.site/api/health` returns JSON HTTP `200` via the Vercel rewrite.

### Step D: Bare Domain (`reqqualityai.site`) + `www` DNS Setup
1. In your domain DNS provider, configure:
   - **Apex (`@` / `reqqualityai.site`)**: `A` record (`76.76.21.21` or Vercel-assigned apex `A`/ALIAS target) **and** configure Vercel Domains so `reqqualityai.site` issues an HTTP `308` permanent redirect to `https://www.reqqualityai.site`.
   - **`www` (`www.reqqualityai.site`)**: `CNAME` record pointing to `cname.vercel-dns.com` (or Vercel's project-specific CNAME target).
2. Verify both hostnames resolve, present valid TLS certificates, and redirect cleanly:
   ```sh
   curl -I https://reqqualityai.site
   curl -I https://www.reqqualityai.site
   ```
   - `https://reqqualityai.site` -> `308` -> `https://www.reqqualityai.site` (no DNS NXDOMAIN or timeout on apex).
   - `https://www.reqqualityai.site` -> `200 OK`.
3. Always sign in at `https://www.reqqualityai.site` (host-only `__Secure-reqquality_*` cookies bind strictly to the canonical origin).

### Step E: Hosted Login & Core Workflow Verification
1. Open `https://www.reqqualityai.site/#login` in a clean browser/incognito window.
2. Inspect DevTools Network on sign in (`POST /api/auth/login`):
   - Returns HTTP `200` (not `426` or `503`).
   - Response sets `Set-Cookie` for `__Secure-reqquality_access` (`Path=/api/; Secure; HttpOnly; SameSite=Lax`) and `__Secure-reqquality_refresh` (`Path=/api/auth/; Secure; HttpOnly; SameSite=Lax`).
   - No `CORS` or blocked-origin errors in Console.
3. Reload the browser page (`F5`): confirm `GET /api/auth/me` stays authenticated (`200`).
4. Run a CSRF-protected write (e.g., save a test draft or AI analysis) and a PDF download (`Export PDF`), then click **Log out** (`POST /api/auth/logout`) and confirm both cookies are cleared.

### Step F: SMTP Invitation & Password-Reset Email Testing
1. Sign in as Admin (`manager` / `admin`), open **Invitations**, and invite a real test inbox you control (as `Analyst` or `SQA Engineer`).
2. Verify API returns HTTP `201` with `delivery_status: "sent"` (not `502` delivery failed).
3. Open the received email and verify the link targets `https://www.reqqualityai.site/accept-invitation?token=...` (not `127.0.0.1` or `localhost`), open it, verify the invited email, and set a 12+ character password to activate the account.
4. On `/#login`, click **Forgot password?**, submit the test account email, open the reset email linking to `https://www.reqqualityai.site/#reset-password?token=...`, complete the reset, and sign in once with the new password.
