# Backlog

Ordered list of remaining work. One item per change, each proven by a check that fails before and passes after.
Update this file in the same commit that finishes an item.

## Direction: HTML-first UI

Prefer native platform features over TypeScript: real `<form>` elements with `required` / `type=email` / `minlength` /
`pattern` and `:user-invalid`, `autocomplete`, `<dialog>`, the Popover API (`popover`) for toasts and menus, `<details>`,
CSS `:has()` / container queries / nesting. Keep Angular bindings and `friendlyError` only where a plain page cannot
talk to the API without script.

## 1. Frontend hosting (top priority, user 2026-11-07)

Goal: a public URL for the frontend (`https://<name>.azurestaticapps.net`). Steps, in order, one commit each:

1. Make the API base URL configurable at build time (currently hard-coded `http://127.0.0.1:8000/api/v1` in `api.service.ts`); `ng serve` must keep working locally. No account needed.
2. Backend CORS: read extra allowed origins from an env var (today only the two localhost origins). No account needed.
3. Terraform `azurerm_static_web_app` (Free, eastus2) plus outputs. User prerequisite: `az provider register --namespace Microsoft.Web --wait`. User runs `terraform apply`.
4. Set the CORS origin on the Container App (Terraform env var) and add the frontend deploy step in CI (SWA deploy token as a GitHub secret; ask the user first).
5. Verify the live site end to end (sign-in against the real API); until then the hosted UI is unverified.

## 2. UI (in order)

1. Login page as a real `<form>`: labels, `type=email`, native validation, Enter submits, `role="alert"` on errors,
   no demo prefills, bootstrap separated from sign-in, separate loading state per form.
2. Workbench page: replace raw JSON output/errors with `friendlyError`, then real forms and result views.
3. Page copy and shell: drop "Feature 1 Workbench" jargon; navigation and sign-out.
4. Success feedback (toast via `popover`, no library) and a responsive layout.
5. Fix stale `src/app/app.spec.ts` ("Hello, app"), then run `ng test` in CI (the `frontend` job only builds today).
6. Frontend calls accept-invite and shows `inviteToken`.

## 3. Deploy hardening

- Tested rollback (needs a second revision; may need revisions-mode multiple and Terraform changes, ask first).
- Branch protection with required checks; a `production` GitHub environment with approval.
- Migrations handling (the entrypoint already runs alembic; unverified against the live Azure Postgres).

## 4. Static analysis

- bandit, then import-linter; one commit each.

## 5. Terraform state and pipeline

- Secrets out of state: ephemeral `random_password` + write-only attributes (verify azurerm 4.81 support).
- Remote encrypted Azure Storage backend (versioning, locking, `init -migrate-state`); needs the user's account.
- Plan on PRs with a read-only identity, then apply behind an approval environment (after remote state).

## 6. Smaller items

- Complexity guardrails (ruff, no new dependency): enable `C901` (mccabe, max-complexity 8) and `PLR0911`/`PLR0912`/`PLR0913`/`PLR0915` (returns, branches, args, statements) in `pyproject.toml`. Measured 2026-11-07: zero findings today, so this is a free ratchet. Test = a throwaway function over the limit fails `ruff check`. Function length by lines has no ruff rule (`PLR0915` counts statements); `lizard` could add NLOC if wanted.
- Review the ~82 lines over 120 for structural causes (long query chains, deep nesting, fat route handlers) before rewrapping blindly. Complexity metrics show nothing wrong, so this is likely long strings/signatures, but it is unverified.
- Resolve the `httpx` vs `httpx2` Starlette deprecation warning.
- Bump Node 20 actions (`actions/checkout@v4`, `setup-python@v5`, `azure/login@v2`) if newer majors exist.
- Dependabot and/or a scheduled pip-audit job (CI only audits at push time).
- Key Vault purge protection and network ACLs.
- Public Postgres plus the Azure-services firewall rule; README note on the cross-region database.
- Clean up the ghost `equitysplitter-pg` servers in eastus2.
- Audit log, password reset, atomic rate limiter; accessibility checks; GitHub repo description/topics.

## Decisions (user, 2026-11-07)

- Ruff line length: shorten from 200; plan is 120 (82 lines to rewrap), revisit 88 later.
- Postgres region: canadacentral (eastus2 failed). Make it the `postgres_location` default in `infra/variables.tf`.
- Frontend errors: the more HTML-native scheme. Inline native validation (`:user-invalid`) plus a `role="alert"` region for server errors; `popover` toasts for confirmations; no library.

## Open decisions (user)

- Do the Terraform state-secrets work before or after the remaining deploy work (leaning after)?

## Not yet verified

- Token behaviour live (the deploy smoke test only hits `/health`).
- Rollback commands.
- That Terraform ignores the image and port changes against real state (run `terraform plan`).
- The CI `pip-audit` step only guards pushes; a CVE published later is caught on the next run.

## Done

- Dependency CVEs: fastapi/starlette, PyJWT, pytest/httpx moved to dev, pip-audit CI gate.
- Intermittent CI failure: SQLite NUMERIC affinity on `postgresql.UUID` in tests (fixed with a `CHAR(32)` hook).
- Login page shows plain-language errors (`friendlyError`).
- `.gitattributes` forces LF for shell scripts (`*.sh text eol=lf`). Requirements-file CRLF warnings remain harmless.
- `@app.on_event` replaced by a lifespan handler (no deprecation warning; startup verified against Postgres).
- alembic `env.py` handles `%` in `DATABASE_URL`.
- Ruff line length is 120 (82 lines rewrapped with `ruff format` on the affected files).
- `postgres_location` defaults to canadacentral (user to confirm with `terraform plan`: expect no changes).
