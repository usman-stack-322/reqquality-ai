# Configured PostgreSQL diagnosis — 2026-10-11

The connection remains blocked at TCP establishment, before PostgreSQL TLS or
authentication. All three resolved addresses time out on port 5432. The exact
blocking device or provider restriction is not established. No evidence supports
changing credentials, disabling TLS, recreating accounts or substituting SQLite.

## Connect-panel comparison supplied by the user

Project: ReqQuality Ai. Branch: production. Database: neondb. The panel's pooled
hostname exactly matches the configured hostname, and the database names match.
This rules out a pooled-hostname/database mismatch against those supplied details.
Project and branch attribution comes from the user's panel selection, not from an
independent Neon API lookup. The user subsequently supplied the exact direct
hostname from the panel. Both official endpoints were tested separately, without
deriving either name or changing DATABASE_URL. Both resolve to three addresses;
all six bounded TCP probes timed out before TLS (pooled: 3,001 ms each; direct:
3,004–3,006 ms). Both read-only psycopg connection attempts also timed out.
Neither SELECT 1 nor the admin-status query executed on either endpoint.
This is a connectivity failure affecting both endpoints, not a pooler-only
failure. Local pooled hostname/database mismatch is ruled out against the
supplied panel details. The exact source of the TCP blocking remains unresolved.
The user's separate PowerShell run reproduced the pooled timeout outside Codex.

## Read-only diagnosis

Run `backend/.venv/Scripts/python.exe backend/diagnose_postgres.py` from the root.
The script outputs only safe status fields. It follows Flask's environment loading
order: inherited environment, then backend/.env, then root .env, without overrides.
It does not invoke application schema initialization or migrations.

- Effective configuration comes from backend/.env; no conflicting root file.
- PostgreSQL connection parameters parse; pooled endpoint, port 5432, sslmode=require.
- Both required persistent secrets satisfy the application's length checks.
- DNS resolves to three addresses.
- Each TCP probe timed out after approximately 3,005–3,006 ms.
- TLS verification is attempted only after TCP succeeds. TCP failed, so neither
  the TLS certificate nor database credentials could be tested.
- A direct psycopg connection with read-only transactions and a three-second
  connection timeout failed after 9,042 ms across the three addresses.
- SELECT 1 did not execute. The subsequent admin-presence/active-status query
  did not execute; those account properties remain unknown.
- Application connection timeout and pool wait are both 10 seconds. Increasing
  either would extend the wait; it would not establish a blocked connection.

The elevated diagnostic and both running Flask processes are outside the identity
targeted by the enabled Codex sandbox firewall block rules. Those rules cannot
explain these probes or the Flask connection failure. The active default route is
Wi-Fi. Earlier HTTPS-port probing to the same host connected on port 443, indicating
the failure is specific to the PostgreSQL port/path, rather than general DNS failure.

The user subsequently reported the same failure on a mobile hotspot. That makes
a restriction unique to the original Wi-Fi network less likely, but does not
identify a device-level filter or provider/path issue. Network egress restrictions
and provider access/status require further evidence to identify the exact source.
No firewall settings were changed.

## Native PowerShell versus Python comparison

Native Test-NetConnection to the confirmed pooled hostname on port 5432 returned
TcpTestSucceeded=false over Wi-Fi. Python socket and psycopg were then checked
against the exact destination address selected by that native test, without
repeating the complete endpoint matrix. Both timed out (socket 3,017 ms;
psycopg 3,016 ms). The read-only query did not execute. This is evidence of a
shared TCP connectivity failure, rather than a Python-only problem.

Read-only security inventory found only the previously documented sandbox-user
outbound block rules, Windows Defender as the registered antivirus, no configured
Windows VPN connection, and no obvious third-party enabled Wi-Fi binding. Defender
Network Protection reports disabled; real-time antivirus remains enabled. These
inventories do not rule out every WFP filter or external security product.
Firewall block logging is disabled, its text log is absent, and the Security event
log could not be read. No security setting or auditing policy was changed.

The user confirms existing Admin login works on the live site. That establishes
that live authentication works; it does not establish local TCP access. Neon's
project/branch IP Allow settings are not accessible through an authenticated
connector here and have been requested from the user. They remain unverified.

Targeted remediation must follow attribution: if Neon IP Allow is enabled and
excludes the local public source IP, add only the approved source IP while retaining
existing production restrictions. If a device/network block is established, have
the responsible administrator permit the required outbound PostgreSQL flow rather
than disabling firewall, antivirus or TLS. No such change has been made or claimed
as a fix. Local query and login remain unsuccessful/unverified respectively.

## Login verification boundary

The live React login path uses /api/auth/login through Vite's HTTP proxy. Requests
reach Flask, but configured-database access still returns safe HTTP 503
database_unavailable before password verification, without authentication cookies.
Successful login, dashboard access, reload persistence and logout against that
database remain unverified. The probe uses synthetic diagnostic credentials; no
existing password was requested, printed or changed.

Only the diagnostic script and this report were added for this investigation.
The script passed Python compilation. No accounts, roles, passwords, connection
settings, database records or production deployment were changed.
