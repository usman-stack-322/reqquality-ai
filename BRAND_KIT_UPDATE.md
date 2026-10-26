# Brand kit applied — 25 October 2026

The supplied `ReqQuality_AI_Brand_Kit.zip` contains six image files and placement
instructions, with no replacement palette or type specification. Its README was
treated as asset-use guidance within the requested branding update. Existing
application colors, workflow, authentication, permissions and prior fixes remain.

- Copied all six assets byte-for-byte to `frontend/public/`.
- Wired the ICO, 32px PNG favicon and Apple touch icon in `frontend/index.html`.
  Kept the existing descriptive page title.
- Replaced the placeholder RQ marks in the shared header and admin sidebar with
  the supplied logo. Added the same mark to the footer, sign-in, invitation,
  invitation-required and password-recovery screens through `BrandLogo.jsx`.
- Logo images use equal width/height, contain sizing and a light backing. Adjacent
  text supplies the accessible brand name, avoiding duplicate screen-reader labels.
- Added a packaged backend copy at `backend/assets/reqquality-logo.png` and a square
  logo tile in every PDF page header. Text remains selectable, margins/page numbers
  remain, and the logo is reused within each PDF rather than fetched remotely.
- Extended the existing isolated browser harness to serve and check brand assets,
  capture the admin sidebar at mobile/desktop widths and accept a separate screenshot
  output directory so prior audit captures need not be overwritten.

Verification: 17 frontend tests passed; production build passed; 13 report tests
passed, including checking an embedded image on every page. Short (3-page) and long
(7-page) PDFs rendered and were visually inspected. All six frontend files and the
backend logo match the supplied ZIP exactly. Real headless Chrome checked loading
and square sizing, icon availability, keyboard/focus, login, roles, saved workflow,
dashboard values and downloads using synthetic users/disposable SQLite and mocked
AI. Results: `audit/brand-frontend-tests.txt`, `audit/brand-build.txt`,
`audit/brand-backend-tests.txt`, `audit/brand-pdf-results.txt`,
`audit/brand-browser-results.txt`; previews in `audit/brand-browser/` and
`audit/brand-pdf/`. No live AI or database access was needed for this visual update.

No migration, account/data change, hosting/DNS/configuration update or deployment.
Start locally using the existing README commands. A browser hard refresh may be
needed for cached favicons after these local files are served or later deployed.
