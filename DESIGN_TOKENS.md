# ReqQuality AI visual system — 26 October 2026

Reference inspected read-only: `C:/Users/ua589/short generation/frontend/src/styles.css`,
`components/Shell.jsx`, `components/AppearanceSelector.jsx`, `public/appearance.js`,
and its index/App files. Existing reference screenshots and the running public
interface on port 5173 were inspected. Reference captures contain only the hero,
excluding sign-in fields and demo credentials. No reference project files changed.

The adaptation uses its 248px sidebar, 65px topbar, 1500px maximum workspace,
32–36px desktop gutters, 12px bordered cards, 8–9px controls/navigation, restrained
purple highlights, and subtle shadows. The split sign-in follows its hero/form
composition while preserving ReqQuality's account and invitation workflows.
Typography requests DM Sans and Manrope with Inter/system fallbacks, as in the
reference. No remote font dependency or extra font package was introduced; actual
glyph rendering depends on fonts available in the browser environment.

The canonical definitions are `frontend/src/theme.css`. Existing layout rules
are in a lower CSS cascade layer so lazy-loaded manager CSS cannot override the
shared theme. Legacy color names are compatibility aliases, not separate palettes.

| Token | Light | Dark |
| --- | --- | --- |
| canvas | `#f5f6fa` | `#111624` |
| surface | `#ffffff` | `#1b2030` |
| surface-alt | `#f8f7fc` | `#242a3b` |
| ink | `#202438` | `#edf0fa` |
| muted | `#697184` | `#b5bfd3` |
| line | `#eaecf2` | `#394154` |
| accent | `#6b58d9` | `#b4a4ff` |
| accent-strong | `#5d49ca` | `#705bd4` |
| accent-tint | `#f2efff` | `#29223f` |
| success / tint | `#16745e` / `#e8f8f3` | `#8de2cd` / `#12392d` |
| warning / tint | `#966315` / `#fff3dc` | `#e8d4b7` / `#392a12` |
| danger / tint | `#b44141` / `#fff0ef` | `#e8bfbf` / `#381412` |

Light success text and the dark primary fill were darkened relative to the
reference for WCAG AA normal-text contrast. Status words/icons remain alongside
colors. Logo backing remains white; logo pixels and proportions are unchanged.

One synchronous `public/appearance.js` controller initializes before React/CSS,
defaults to System, validates localStorage values, follows OS changes only in
System mode, and handles denied storage. `ThemeSelector` listens to its updates;
switches do not remount forms or change navigation. The preference survives login,
logout and reload locally, without storing anything in the database. Reduced-motion
preferences disable decorative animation and transitions. PDF styling is independent
and stays print-friendly.
