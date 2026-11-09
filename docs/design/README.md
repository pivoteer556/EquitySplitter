# Design

Visual design assets for EquitySplitter. These are design explorations, not specifications: behaviour is defined in `docs/specs/`.

## Logo

Three concepts for the mark, each drawn on a 64 by 64 grid (see `logo/`):

| File | Idea |
| --- | --- |
| `equitysplitter-mark-a-shares.svg` | A house cut into three vertical slices of unequal width. Each slice is one owner's share. Preferred. |
| `equitysplitter-mark-b-offset.svg` | A house cut in two, with the right half shifted down. |
| `equitysplitter-mark-c-ledger.svg` | A roof over three bars of decreasing length, a reference to the equity ledger. |

Palette: navy `#14213D`, blue `#3A5FB0`, amber `#E0A800`. On dark backgrounds use `#E9EDF5`, `#7FA3E6`, `#F2C94C`. In the app (2026-11-09, BACKLOG item 12) the page is night `#0E1626` with text `#E9EDF5` and links `#7FA3E6`, and cards and panels are firelit cream `#F8EDCB` with an amber border `#D9B96A` and navy text; this is the only theme, and a `prefers-color-scheme` dark-mode variant is not done. The header and logo sit directly on night, so the wordmark and the navy part of the mark use `#E9EDF5` and the blue part uses `#7FA3E6`. Wordmark: Bricolage Grotesque, "Equity" at weight 500 and "Splitter" at weight 800.

## Screens

Three app screens were designed against the specs, using sample data only:

- Officer: property list (address, owner count, agreement acknowledgement progress, loan amount, status).
- Officer: property detail (ownership caps per owner, who has acknowledged, agreement terms in plain language, loan summary).
- Buyer: listings (address, status and listed date only, plus a directory of professionals to ask).

Exports of the screens belong in `screens/` when added.
