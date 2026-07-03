# ADR-002: Composite view for shared hypothesis trees

## Status

Accepted (2026-07-03)

## Context

Several code repositories can contribute different hypothesis branches under the
same research problem (e.g. diversity bonus in `verl-agent-craftext` and external
operator in `TalkingHeads`). ResearchOS previously rendered one tree per project;
programs only grouped projects in the sidebar.

No single repository should be “dominant”: each repo owns its fragment of the tree
and syncs `koi-structure/` on its own orphan branch.

## Decision

1. **Grouping key:** optional frontmatter field `composite_id: <slug>` on
   `koi-structure/project.md`.
2. **Merge rule:** all discovered projects with the same `composite_id` (≥2 members)
   are merged at **read time** by node id. Shared ancestors (`problem`, `cause`) are
   duplicated in each repo with identical ids; unique branches live in one repo each.
3. **API:**
   - `GET /composites` — list composite groups
   - `GET /composites/{composite_id}` — merged tree + boards + members + conflicts
4. **UI:** program sidebar shows a virtual entry (⎇ title) above member projects;
   opening it loads the composite view. Writes route to the owning repo via
   `node.project_id` / `board.source_project_id`.
5. **Conflicts:** if shared node ids differ across repos (title, parent, type,
   description), API returns a `conflicts` array; first member wins for display.

## Format example

```yaml
---
id: talking-heads
composite_id: llm-ood-decision-making
programs:
  - id: мультимодальное-обучение-с-подкреплением
---
```

Each member repo includes shared nodes plus its own remediation/method subtrees.

## Consequences

- Storage stays per-repo; composite is a view layer only.
- `PUT /projects/{id}` unchanged; composite id is not a writable project id.
- Literature / agent chat in composite view use the first member project (MVP).
- Future: broadcast PATCH for shared nodes; hide member projects when composite exists.

## References

- `koi/services/composite.py`
- `api/routers/composites.py`
- `ReseachOS/web/app.js` — composite sidebar + write routing
