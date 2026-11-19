# Smells register

The EquitySplitter findings from the code-smell checklist (`Smells.md`), what was triaged high or low, and what was done about each. The checklist and the triage rules are generic and live in `Smells.md`; this file holds the project-specific state.

## Current register (2026-11-10, updated 2026-11-11: no open high-priority rows)

High priority:

| Smell | Why high |
|---|---|
| (none open) | The register has no open high-priority rows as of 2026-11-11. |

Low priority (parked):

| Smell | Why low |
|---|---|
| `# noqa: PLR0913` on `list_professionals` (limit and offset repeated on list routes) | Contained, cosmetic. A shared paging dependency is a tidy-up, not urgent. |
| Copied e2e preambles, repeated 1100 ms waits and repeated rotation test helpers | Test-only. The route-level rotation work (done 2026-11-10) added one shared test file, `tests/test_session_rotation_by_default.py`; the older per-endpoint rotation test files remain and could now be folded into it. |
| Unreachable "institution id is None" check in `create_institution` and the unreachable 404 in revoke | Dead code with no effect; remove when next touching those functions. |
| Stale comment at `app/api/routes/auth.py:377` | Misleading comment only. |
| Comma-separated lists | Checked 2026-11-10: no id lists anywhere in the API, schema or UI. The only comma-separated value is the `CORS_ALLOW_ORIGINS` environment variable, which is configuration. Keep out of new APIs; no action now. |

Process rule (apply to every new migration; no present harm, so not in either table):

- Non-planar database layout. Before merging a migration that adds a table or foreign key, check that the new link does not duplicate an existing path or add a cycle; run the planarity check when a table has more than a few links.

Resolved:

- 2026-11-10, session-token rotation as a per-endpoint call (`rotate_session` in about 20 handlers, plus dead rotating dependencies). Fixed by moving rotation into one place: `RotatingRoute` (`app/api/route.py`) rotates after the response, only below status 400, and the handlers carry no rotation code. `rotate_session`, the `*_unrotated` dependencies and the dead rotating dependencies are gone; a test enforces that every router uses `RotatingRoute`.
- 2026-11-10, extra queries after rotation on two older list endpoints (`property_listings.list_listings`, the buyer connection-requests list). Resolved by the same change: the cause was rotating (and committing) inside the handler before serialization, and that no longer happens.
- 2026-11-11, the missing-or-forbidden property smell and the repeated ownership checks (and the malformed-id `500` on `attach_agreement`, `invite_owner` and `acknowledge_agreement`). The user decided the rule: a missing object is a 404 and a forbidden one is a 403, everywhere; IDOR is answered by unguessable UUID ids plus an authorization check on every lookup, not by hiding existence. Fixed by one lookup, `load_property` (`app/api/deps/properties.py`), used by every handler that loads a property; an officer of another institution now gets 403 (was 404) on the read, update, delete, owners and listing routes.
- 2026-11-11, the unhandled `IntegrityError` (500) on a duplicate officer email at `POST /institution-users`. Now `409 Email already registered`, same as `register`, through one helper (`ensure_officer_email_free`, `app/services/auth.py`) plus an `IntegrityError` backstop; `bootstrap_institution` shares the helper but still has no backstop (a true race stays a 500, low priority).
- 2026-11-11, officer, owner-invite and bootstrap emails normalized inconsistently (a mixed-case officer could never sign in; the same buyer could become two rows). Fixed once: every request schema that takes an email uses `normalize_email` (`app/schemas/types.py`) through `NormalizedEmail` or `NormalizedEmailStr`, and a generic test checks every `*Create` or `*Request` model with an email field. The database columns are still case-sensitive (a `citext` or `lower(email)` index is a possible hardening); live data had 0 uppercase emails (user check, 2026-11-11).

Test smells already handled or tracked:

- The flaky `security.spec.ts` fill race (a fill racing form initialisation) is being fixed, so it is not parked.
- "Tests that cannot fail": the rotation e2es are now checked against the old backend before they are accepted. Keep doing that.
