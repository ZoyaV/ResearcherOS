# ResearchOS architecture guardrails

## Current system boundaries

Use these as dependency-direction defaults. Verify actual imports before every phase.

| Area | Owns | Must avoid |
|---|---|---|
| `api/routers/` | HTTP parsing, status codes, response mapping, dependency lookup | project mutation rules, filesystem workflows, long orchestration |
| `koi/projects/` | project commands, read models, reports, live artifacts, kanban, and sync/discovery orchestration | HTTP types, unrelated capabilities, persistence details leaking into callers |
| `koi/laboratory/` | cross-project programs, membership, summaries, and portfolio grouping | raw persistence mechanics, HTTP types, single-project mutation policy |
| `koi/application/` | cross-feature use cases and transitional compatibility facades | becoming a permanent bucket for feature-specific workflows |
| `koi/core/` | domain operations, validation, deterministic transformations | FastAPI, process-wide state, direct filesystem/network access where a boundary can be passed in |
| `koi/adapters/` | persistence, serialization, external-system and filesystem integration | deciding domain policy |
| `koi/services/` | existing higher-level capabilities awaiting deliberate classification | becoming a default destination for unrelated logic |
| `web/api.js` | browser transport to the backend | feature state and rendering policy |
| `web/*.js` | feature behavior, state, and rendering with explicit ownership | growing `web/app.js` through new feature logic or creating circular globals |
| `hub/` | hub-specific application and static UI | importing private implementation details from unrelated features |

Dependencies should generally point inward: transport/UI → application → core, with adapters supplied at boundaries. Do not force this pattern where a simpler pure module is clearer; document exceptions.

## Known pressure points

- `web/app.js` and `web/styles.css` are decomposition projects, not single-file moves. Extract one user-visible feature at a time.
- `koi/services/` contains multiple capability families. Classify files by responsibility and coupling before proposing subpackages.
- Public API routes, scripts, serialized Markdown/JSON, workspace layout, and browser globals may be compatibility surfaces even when Python imports do not reference them.
- Existing wrappers may intentionally protect callers during staged migration. Thin wrappers are debt with a removal condition, not automatically dead code.

## Target-structure decision test

Create or rename a package only if at least two of these are true:

1. It owns a coherent domain or use case.
2. It can expose a small stable interface.
3. Its internals change for reasons different from neighboring code.
4. It can be tested largely through its public boundary.
5. Moving it improves dependency direction rather than merely shortening a file.

Reject a proposed split if it only distributes one tightly coupled procedure across more files.

## Verification ladder

Run the cheapest relevant check first and broaden after it passes:

1. A focused test file or test selector for the changed behavior.
2. Contract tests for affected application commands and API routes.
3. `PYTHONPATH=. .venv/bin/pytest -q` for the backend suite when the repository virtualenv exists; otherwise use the active environment's `python -m pytest -q`.
4. A browser or executable smoke check for every changed frontend flow. If none exists, add a focused characterization harness before a risky extraction.
5. Repository-wide `rg` searches for old imports, function names, DOM globals, routes, filenames, and script entry points.
6. `git diff --check`, `git diff --stat`, and review of the complete diff.

Do not substitute compilation, coverage percentage, or a successful import for observable-behavior checks.

## Phase shape

A safe phase normally follows this sequence:

1. Protect current behavior.
2. Introduce a seam or destination module.
3. Delegate through the existing interface.
4. Move one responsibility.
5. Migrate known consumers.
6. Verify and search for stragglers.
7. Remove the facade only when deletion criteria are satisfied.

Name phases by the responsibility gained, not by folders moved: for example, "isolate project command orchestration" rather than "create application directory".
