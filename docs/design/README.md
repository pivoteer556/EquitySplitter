# Design

Visual design assets for EquitySplitter. These are design explorations, not specifications: behaviour is defined in `docs/specs/`.

## Logo

The chosen logo is the lockup `logo/equitysplitter-lockup.svg` (house mark plus the "EquitySplitter" wordmark as outlines, "Splitter" drawn as a navy top half and blue bottom half); the mark-a/b/c files below are earlier concept drafts.

Three concepts for the mark, each drawn on a 64 by 64 grid (see `logo/`):

| File | Idea |
| --- | --- |
| `equitysplitter-mark-a-shares.svg` | A house cut into three vertical slices of unequal width. Each slice is one owner's share. Preferred. |
| `equitysplitter-mark-b-offset.svg` | A house cut in two, with the right half shifted down. |
| `equitysplitter-mark-c-ledger.svg` | A roof over three bars of decreasing length, a reference to the equity ledger. |

Palette: navy `#14213D`, blue `#3A5FB0`, amber `#E0A800`. In the app (2026-11-09, BACKLOG item 13, which supersedes the night page of item 12; page blue cooled in item 14) the page is light blue `#9FC4EE` with navy text and darker blue `#2A4688` links, and cards and panels are firelit cream `#F8EDCB` with an amber border `#D9B96A` and navy text. The header carries the logo lockup in navy, blue and amber directly on the page; the lockup includes the wordmark, so the header no longer uses Bricolage Grotesque. The dark-background variants (`#E9EDF5`, `#7FA3E6`, `#F2C94C`) are not used by the app at present. This is the only theme; a `prefers-color-scheme` dark-mode variant is not done (planned). Focus ring and header rule (2026-11-10, BACKLOG item 9, applied as the recommended default, pending the user's confirmation): the keyboard focus ring (buttons, links, inputs, selects, `summary`; 3px outline, 2px offset) is navy through the one token `--focus-ring` in `src/styles.css`, 8.8:1 on the page and 13.7:1 on cream (amber was 1.18:1 and 1.84:1, below the 3:1 minimum for non-text UI). The header bottom rule is `--brand-blue-dark`, 5.0:1 on the page (amber was 1.19:1). The amber logo mark is unchanged and deliberately exempt from the audit (it is a logo). To revert to amber, point `--focus-ring` at `--brand-amber` (focus ring) and restore `var(--brand-amber)` in the header rule in `app.css`. The guard is `frontend/app/e2e/contrast.spec.ts` (7 tests: it measures the app's own computed colours, so a revert makes it fail on purpose). The `--brand-font` token and the Google Fonts link were removed because nothing used them. Planned, not done: tokens for the raw colours still in component CSS (error box `#7f1d1d` on `#fef2f2`, `pre` `#0f172a` on `#e2e8f0`, `.meta` and `.value` `#334155`/`#0f172a`; they pass AA but are not tokens).

## Screens

Three app screens were designed against the specs, using sample data only:

- Officer: property list (address, owner count, agreement acknowledgement progress, loan amount, status).
- Officer: property detail (ownership caps per owner, who has acknowledged, agreement terms in plain language, loan summary).
- Buyer: listings (address, status and listed date only, plus a directory of professionals to ask).

Exports of the screens belong in `screens/` when added.
