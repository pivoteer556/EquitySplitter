# Code smells

A code smell is a sign that the code has a maintenance problem. It is not a bug by itself. It is a reason to
look closer before the next change, and the usual response is to consolidate or simplify, not to patch around it.

Each entry says what to look for and why it hurts. This file is a generic checklist: it names no project, file or
date, so it can be copied into any repository. Findings and decisions about a particular codebase belong in that
codebase's own register, not here.

## Signs of duplicated behavior

Four reliable signals that the same behavior lives in more than one place. If any of them fires, look for the shared
cause and fix it once.

1. **The code does something it shouldn't.** A bug that exists because a rule was copied into some places and missed
   in others.
2. **The same or a similar change has to be applied many times to fix one issue.** This is also called shotgun
   surgery. If the fix for one bug is a list of near-identical edits, the code was duplicated.
3. **Two things that should behave consistently don't.** The same bad input is rejected one way on one route and a
   different way on another, or two schemas validate the same field two different ways.
4. **The same condition appears again and again.** The same two-condition `if` in three places, or the same
   condition of three or more clauses in two places, usually means one rule copied into several places. Look for
   the shared rule and give it a name (a predicate or a helper) so a change to the rule is made once.
   - How to look: normalise each condition (ignore whitespace and the order of its operands) and count matches
     across the whole repository, not just within one file. A parser or AST walk is more reliable than a text search,
     which misses reordered or reformatted copies.
   - A hit means the code deserves a look, not a fix. Guard clauses on different data, and conditions that only look
     alike, are fine.

## Data and interfaces

- **Comma-separated ID lists.** A list of ids packed into one string (`"12,57,903"`) in a column, a query parameter
  or a field. It has to be split and parsed everywhere it is used, nothing checks that each part is valid, an id
  containing the separator breaks it, you cannot join on it or index it, and "does this contain id 57" becomes a
  string search that also matches 157. Use a real list in the API (a JSON array or repeated parameters), and a join
  table or an array type in the database.
- **Stringly-typed values.** Ids, dates, enums and amounts passed around as plain strings and parsed late, wherever
  they happen to be used. The parse can fail far from where the value came in. Declare the type at the edge so the
  framework rejects bad input with a clear client error instead of a server error.
- **Boolean flag parameters.** `do_thing(x, True, False)` says nothing at the call site, and the function is really
  two functions. Split it, or use named options.
- **Long parameter lists.** More than about five parameters usually means a missing concept (a request object, a
  paging object). A lint suppression for argument count is a smell marker.
- **Magic numbers and strings.** The same literal (a status code, a state name, a role name) repeated in several
  files. Name it once.
- **Null as a hidden mode.** `None` means "do the default thing" in one place and "missing" in another.
- **Non-planar database layout.** A layout is planar when its entity-relationship graph (tables as nodes, foreign
  keys as edges) can be drawn on a flat page with no crossing lines. A non-planar one cannot, which is a sign of a
  tangled schema: a hub table that everything references, a shortcut link that repeats a path that already exists
  (A references B, B references C, and A also references C), circular foreign keys, or a many-to-many knot between
  several tables. It hurts because there are two ways to get from A to C that can disagree, cascade deletes surprise
  you, the diagram is hard to explain, a change ripples through many tables, and a redundant link can contradict the
  long way round. Prefer a tree or layered layout: model each fact once and hang details off their owner, break a
  hub by splitting its roles, replace a redundant shortcut with a derived query or a view, make a many-to-many an
  explicit join table with its own meaning, and give every relationship one owner direction so there are no cycles.
  - How to check: export the table and foreign-key list (from the models or the database), build the graph, and run a
    planarity test (a standard graph algorithm; `networkx.check_planarity` does it, and with `counterexample=True` it
    returns the tangled subgraph). A quick necessary check first: a simple planar graph with V >= 3 tables has at
    most 3V - 6 edges, so more than that is non-planar for certain. Passing the edge bound proves nothing.
  - Process rule: before merging a migration that adds a table or foreign key, check that the new link does not
    duplicate an existing path or add a cycle, and run the planarity check when a table has more than a few links.

## Behavior and control flow

- **Hidden side effects.** A function whose name says it reads or checks but which also writes. Dependencies and
  getters are the usual offenders.
- **Temporal coupling.** Steps that only work in a certain order, with nothing enforcing it, so a caller can get it
  wrong.
- **Swallowed or unhandled errors.** An empty `except`, or no handling where one is needed, so a predictable failure
  (a duplicate key, a missing row) becomes a server error.
- **Long function or god function.** One function that validates, queries, decides, writes and formats. It is hard to
  test one part alone and easy to change the wrong part.
- **Feature envy.** A function that mostly reaches into another object's data. The logic belongs next to that data.
- **Deep nesting and long if-chains.** Early returns and small helpers flatten them.
- **Inconsistent layering.** Route handlers doing database work, query details leaking into schemas, or business rules
  that exist only in the UI.

## Dead and misleading code

- **Dead code.** Functions, parameters or branches nothing calls. They still have to be read, and someone will call
  them by accident.
- **Comments that say what, not why, and stale comments.** A comment that restates the next line adds nothing. A
  comment that is now wrong is worse than none.
- **Speculative generality.** Hooks, options and abstractions for a future that has not arrived.
- **Duplicated tests and fixtures.** The same setup pasted into many test files. When behavior changes, every copy
  has to change.

## Tests

- **A test that cannot fail.** It passes before the fix too. If you have not seen a test fail, you do not know it
  tests anything. Plant the mistake, or run the test against the old code, before trusting it.
- **Sleeps and timing assumptions.** A fixed wait to make a race go away, or a test that depends on the clock or on
  step boundaries. Wait for a condition, or control the clock.
- **Flaky tests.** A test that sometimes fails for no code reason trains everyone to ignore red builds. Find the race
  and fix it, do not just rerun.
- **Shared mutable state between tests.** Order-dependent tests, or a shared database row.
- **Testing the implementation, not the behavior.** Tests that break on a harmless refactor.

## Performance

- **N+1 queries.** One query for a list, then one more per row, often hidden behind lazy loading or an expired
  object.

## Triage: investigate now or later

Triage decides where a smell goes. The owner of the code can overrule any call.

**High priority: investigate now.** A smell is high priority if ANY of these holds:

1. **It can hurt users or data today.** A security, privacy, data-integrity or correctness effect, including an
   unhandled error that returns a server error to a real request.
2. **It multiplies.** Every new feature or endpoint adds another copy or another way to get it wrong, so the cost of
   leaving it grows.
3. **It is cheap now and expensive later.** It sits in a public API shape, a database schema or a stored value, where
   changing it later means migrations, clients or data fixes.
4. **It blocks planned work.** The next backlog item would have to build on it or copy it.

**Low priority: investigate once the outstanding questions are done.** All of these hold: it is contained to one
place, it does not grow with new work, it has no user-visible or data effect, and nothing planned touches it. Cosmetic
and stylistic smells are low priority unless they hide one of the high-priority cases.

Tie-breaker: when unsure, ask whether a new teammate adding the next endpoint would copy the smell. If yes, it is high.

A high-priority smell becomes the top of the backlog as its own item (with an example), and the next piece of work
takes it before ordinary feature work. A low-priority smell is written down in the project's register and in the
backlog's parking section, and nothing more.

## How to use this file

When something feels wrong, or you are about to make the same edit a second time, check the list. If a smell fits,
write it into the backlog as its own item (with an example) rather than patching around it, and prefer one
consolidating change over many copies of a fix. Keep this file generic: add a new smell here with a short
description of what to look for and why it hurts, and record where it was found, and what was done, in the project's
register.
