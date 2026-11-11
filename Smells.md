# Code smells

A code smell is a sign that the code has a maintenance problem. It is not a bug by itself. It is a reason to
look closer before the next change, and the usual response is to consolidate or simplify, not to patch around it.

Each entry says what to look for, why it hurts, and (where we have one) an example from this repo.

## Signs of duplicated behavior

Three reliable signals that the same behavior lives in more than one place. If any of them fires, look for the shared
cause and fix it once.

1. **The code does something it shouldn't.** A bug that exists because a rule was copied into some places and missed
   in others.
   - Example: the session token was rotated before the request was validated, so a rejected request left the browser
     with a dead token. A successful revoke returned a fresh token that the same call had just revoked.
2. **The same or a similar change has to be applied many times to fix one issue.** This is also called shotgun
   surgery. If the fix for one bug is a list of near-identical edits, the code was duplicated.
   - Example: the token-rotation fix was applied to about 20 endpoints one at a time, each a copy of the last.
3. **Two things that should behave consistently don't.**
   - Example: a malformed id is a 404 on one route, a 422 on another and a 500 on a third. A duplicate email is a 409
     on `register` and a 500 on `POST /institution-users`. The same missing-or-forbidden property is a 404 for an
     officer and a 403 for a buyer.

## Data and interfaces

- **Comma-separated ID lists.** A list of ids packed into one string (`"12,57,903"`) in a column, a query parameter
  or a field. It has to be split and parsed everywhere it is used, nothing checks that each part is valid, an id
  containing the separator breaks it, you cannot join on it or index it, and "does this contain id 57" becomes a
  string search that also matches 157. Use a real list in the API (a JSON array or repeated parameters), and a join
  table or an array type in the database.
- **Stringly-typed values.** Ids, dates, enums and amounts passed around as plain strings and parsed late, wherever
  they happen to be used. The parse can fail far from where the value came in.
  - Example: `UUID(propertyId)` inside handlers, which raises a 500 on bad input. Declare the type at the edge so the
    framework rejects it with a 422.
- **Boolean flag parameters.** `do_thing(x, True, False)` says nothing at the call site, and the function is really
  two functions. Split it, or use named options.
- **Long parameter lists.** More than about five parameters usually means a missing concept (a request object, a
  paging object). A lint suppression for argument count is a smell marker.
  - Example: `list_professionals` needed `# noqa: PLR0913` because `limit` and `offset` are repeated on every list
    route instead of living in one paging dependency.
- **Magic numbers and strings.** The same literal (`200`, `"pending_acknowledgement"`, `"institution_user"`) repeated
  in several files. Name it once.
- **Null as a hidden mode.** `None` means "do the default thing" in one place and "missing" in another.

## Behavior and control flow

- **Hidden side effects.** A function whose name says it reads or checks but which also writes. Dependencies and
  getters are the usual offenders.
  - Example: an authentication dependency that also rotated and committed the stored session token.
- **Temporal coupling.** Steps that only work in a certain order, with nothing enforcing it, so a caller can get it
  wrong.
  - Example: rotating the session commits the transaction, which expires every loaded row. Serialize first and rotate
    last, or every row is re-queried.
- **Swallowed or unhandled errors.** An empty `except`, or no handling where one is needed. The unhandled
  `IntegrityError` on a duplicate officer email is the second kind.
- **Long function or god function.** One function that validates, queries, decides, writes and formats. It is hard to
  test one part alone and easy to change the wrong part.
- **Feature envy.** A function that mostly reaches into another object's data. The logic belongs next to that data.
- **Deep nesting and long if-chains.** Early returns and small helpers flatten them.
- **Inconsistent layering.** Route handlers doing database work, query details leaking into schemas, or business rules
  that exist only in the UI.

## Dead and misleading code

- **Dead code.** Functions, parameters or branches nothing calls. They still have to be read, and someone will call
  them by accident.
  - Example: the plain rotating auth dependencies, once every route had moved to the unrotated ones, and an
    unreachable "institution id is None" check.
- **Comments that say what, not why, and stale comments.** A comment that restates the next line adds nothing. A
  comment that is now wrong is worse than none.
- **Speculative generality.** Hooks, options and abstractions for a future that has not arrived.
- **Duplicated tests and fixtures.** The same setup pasted into many test files. When behavior changes, every copy
  has to change.

## Tests

- **A test that cannot fail.** It passes before the fix too. If you have not seen a test fail, you do not know it
  tests anything.
  - Example: a rotation e2e that passed against the old backend because two calls landed in the same second.
- **Sleeps and timing assumptions.** A fixed wait to make a race go away, or a test that depends on the clock or on
  step boundaries. Wait for a condition, or control the clock.
- **Flaky tests.** A test that sometimes fails for no code reason trains everyone to ignore red builds. Find the race
  and fix it, do not just rerun.
  - Example: a fill that raced the page's form initialisation, leaving a disabled button for 30 seconds.
- **Shared mutable state between tests.** Order-dependent tests, or a shared database row.
- **Testing the implementation, not the behavior.** Tests that break on a harmless refactor.

## Performance

- **N+1 queries.** One query for a list, then one more per row, often hidden behind lazy loading or an expired
  object.
  - Example: returning rows after the commit that rotates the token re-queried every row.

## Triage: investigate now or later

Triage decides where a smell goes. The user delegated this call to Claude (2026-11-10); the user can overrule any
entry.

**High priority: investigate now.** A smell is high priority if ANY of these holds:

1. **It can hurt users or data today.** A security, privacy, data-integrity or correctness effect, including an
   unhandled error that returns a 500 to a real request.
2. **It multiplies.** Every new feature or endpoint adds another copy or another way to get it wrong, so the cost of
   leaving it grows.
3. **It is cheap now and expensive later.** It sits in a public API shape, a database schema or a stored value, where
   changing it later means migrations, clients or data fixes.
4. **It blocks planned work.** The next backlog item would have to build on it or copy it.

**Low priority: investigate once we are down to outstanding questions.** All of these hold: it is contained to one
place, it does not grow with new work, it has no user-visible or data effect, and nothing planned touches it. Cosmetic
and stylistic smells are low priority unless they hide one of the high-priority cases.

Tie-breaker: when unsure, ask whether a new teammate adding the next endpoint would copy the smell. If yes, it is high.

A high-priority smell becomes the top of the backlog as its own item (with the example), and the next MAGI run takes
it before ordinary feature work. A low-priority smell is written down here and in the backlog's parking section, and
nothing more.

### Current register (2026-11-10)

High priority:

| Smell | Why high |
|---|---|
| Malformed ids give 404, 422 or 500 depending on the route (`attach_agreement`, `invite_owner`, `acknowledge_agreement` still 500) | A 500 on bad input, and an inconsistent API contract that is cheap to settle now. |
| A missing property is a 404 for an officer of another institution but a 403 for an unlinked buyer | Two answers for the same case. Rule decided by the user 2026-11-11: missing is 404, forbidden is 403 (an IDOR concern is answered by unguessable UUIDs and an authorization check on every lookup, not by hiding existence). Implement it in one lookup helper. |
| Duplicate officer email on `POST /institution-users` is an unhandled `IntegrityError` (500), while `register` and `bootstrap_institution` return 409 | A 500 for a real request, and inconsistent with the sibling routes. Small fix. |
| Property-ownership checks rewritten in each handler | Multiplies, and feeds the 404/403 inconsistency above. Same fix. |

Low priority (parked):

| Smell | Why low |
|---|---|
| `# noqa: PLR0913` on `list_professionals` (limit and offset repeated on list routes) | Contained, cosmetic. A shared paging dependency is a tidy-up, not urgent. |
| Copied e2e preambles, repeated 1100 ms waits and repeated rotation test helpers | Test-only. The route-level rotation work (done 2026-11-10) added one shared test file, `tests/test_session_rotation_by_default.py`; the older per-endpoint rotation test files remain and could now be folded into it. |
| Unreachable "institution id is None" check in `create_institution` and the unreachable 404 in revoke | Dead code with no effect; remove when next touching those functions. |
| Stale comment at `app/api/routes/auth.py:377` | Misleading comment only. |
| Comma-separated lists | Checked 2026-11-10: no id lists anywhere in the API, schema or UI. The only comma-separated value is the `CORS_ALLOW_ORIGINS` environment variable, which is configuration. Keep out of new APIs; no action now. |

Resolved:

- 2026-11-10, session-token rotation as a per-endpoint call (`rotate_session` in about 20 handlers, plus dead rotating dependencies). Fixed by moving rotation into one place: `RotatingRoute` (`app/api/route.py`) rotates after the response, only below status 400, and the handlers carry no rotation code. `rotate_session`, the `*_unrotated` dependencies and the dead rotating dependencies are gone; a test enforces that every router uses `RotatingRoute`.
- 2026-11-10, extra queries after rotation on two older list endpoints (`property_listings.list_listings`, the buyer connection-requests list). Resolved by the same change: the cause was rotating (and committing) inside the handler before serialization, and that no longer happens.

Test smells already handled or tracked:

- The flaky `security.spec.ts` fill race (a fill racing form initialisation) is being fixed, so it is not parked.
- "Tests that cannot fail": the rotation e2es are now checked against the old backend before they are accepted. Keep doing that.

## How to use this file

When something feels wrong, or you are about to make the same edit a second time, check the list. If a smell fits,
write it into `BACKLOG.md` as its own item (with the example) rather than patching around it, and prefer one
consolidating change over many copies of a fix. New smells found in this repo can be added here with a one-line
example.
