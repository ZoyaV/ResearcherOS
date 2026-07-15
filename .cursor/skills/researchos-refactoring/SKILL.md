---
name: researchos-refactoring
description: Safely plan and execute structural refactors in ResearchOS while preserving behavior. Use for reorganizing api/, koi/, web/, or hub/; splitting large modules such as web/app.js or web/styles.css; moving responsibilities between routers, application commands, domain logic, adapters, and services; reducing coupling; or deleting suspected compatibility code. Also use when a proposed cleanup changes imports, module ownership, package boundaries, or public interfaces.
---

# ResearchOS Refactoring

Restructure ResearchOS through evidence-backed, reversible slices. Treat green tests as a starting signal, not proof that an untested UI or integration cannot regress.

Read `references/architecture-guardrails.md` before planning or changing architecture.

## Classify the request

- For diagnosis, review, or a plan: inspect read-only and stop after presenting evidence and a phased plan.
- For an explicitly requested implementation: plan first, then implement only the smallest coherent phase.
- For a broad request such as "clean up the architecture": prepare the target boundaries and phase sequence, then obtain confirmation before moving files.
- Do not commit, push, tag, or remove compatibility surfaces unless the user explicitly authorizes it.

## Establish the baseline

1. Read `agent/AGENTS.md`, `agent/onboarding/repo-map.md`, and `docs/agent/domain-model.md`.
2. Check `git status --short --branch`. Preserve unrelated user changes.
3. Inventory the affected files, imports, callers, routes, scripts, tests, and data formats with `rg` and `rg --files`.
4. Run the narrow relevant tests and the full backend suite. Record the result before edits.
5. Identify gaps around the exact behavior to be moved. Add characterization or contract tests before restructuring an inadequately protected area.

Never use file count alone as a reason to create a package. Split only when a stable responsibility, dependency boundary, or independently testable behavior is identifiable.

## Produce the refactor plan

For each phase, state:

- the responsibility being isolated;
- current owners and every known consumer;
- the intended destination and allowed dependency direction;
- behavior and interfaces that must remain unchanged;
- tests to add before the move and checks to run afterward;
- compatibility facade, if callers cannot migrate atomically;
- rollback point and deletion criteria.

Keep phases independently mergeable. Prefer extracting behavior behind the existing interface before changing callers or names. Separate behavior changes from structural moves.

## Create a safety net

- Pin observable current behavior at the closest stable boundary: domain function, application command, HTTP contract, serialized project file, or browser-visible interaction.
- Characterize only the change area and one layer of callers/callees, not the entire repository.
- Mark suspicious current behavior rather than silently correcting it during a structural change.
- Introduce the narrowest seam for hard-coded I/O, time, randomness, globals, or browser state. Prefer an explicit function parameter or small adapter over permanent module mocking.
- For frontend work, protect the affected user flow before extracting code from `web/app.js`; backend pytest coverage alone is insufficient.

## Execute one slice

1. Add or strengthen the safety test and make it pass against the old structure.
2. Extract one responsibility without changing its observable behavior.
3. Preserve the old import or call surface with a thin compatibility facade when consumers remain.
4. Migrate consumers deliberately and search again for old references.
5. Run focused tests after each meaningful edit, then the full required checks.
6. Inspect the diff for accidental formatting churn, duplicated logic, new cycles, and unrelated changes.
7. Report the completed slice and remaining compatibility debt before starting another phase.

If a check fails, stop and determine whether the baseline, the test, or the refactor is responsible. Do not weaken assertions merely to recover green status.

## Delete safely

Delete a file, wrapper, export, or branch only when all conditions hold:

- repository-wide search finds no runtime, script, template, or test consumer;
- the replacement behavior has direct tests;
- no documented external or compatibility contract requires it;
- full verification passes without it;
- the deletion is included explicitly in the approved phase.

Generated files, workspace data, queues, and user artifacts are not cleanup targets.

## Completion gate

A phase is complete only when:

- behavior-preserving tests pass;
- dependency direction is clearer and no new cycle exists;
- each moved responsibility has one obvious owner;
- compatibility debt is documented or removed under the deletion rules;
- the working tree contains only intended changes;
- the final report lists changed boundaries, verification performed, and remaining risks.

Do not claim the architecture refactor is complete while a large compatibility facade still owns business logic or while the protected user flow lacks an executable check.
