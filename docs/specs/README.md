# Design specs

Rule: **Any change to the schema, API, auth or roles updates these docs in the same commit.**

| File | Covers | Status | Last synced |
|---|---|---|---|
| `shared_mortgage_feature1_spec.docx` | Feature 1, Property Setup: closed decisions, schema, property endpoints, acceptance criteria, backlog. Ends with a change log. | Current | 2026-11-07 |
| `shared_mortgage_feature2_auth_spec.docx` | Feature 2, Authentication and Authorization: threat model, closed decisions (Argon2id, rate limits, invites), auth schema, JWT claims, endpoints, acceptance criteria. Ends with a change log. | Current | 2026-11-07 |
| `updated_mortgage_schema.html` | Current ER diagram, matching `app/models` and migrations 0001-0007. | Current | 2026-11-07 |
| `shared_mortgage_equity_schema.html` | Original ER diagram (retired OWNERSHIP model). | Superseded by `updated_mortgage_schema.html`; kept for history | n/a |

Built in part: buyer-initiated connection requests (create and list, migration 0007). Not built yet and only labelled as planned in the docs: accepting, declining and cancelling them (see `BACKLOG.md` section 2e), NMLS information for professionals, invite email delivery, password reset, and dropping the legacy loan columns from `properties`.
