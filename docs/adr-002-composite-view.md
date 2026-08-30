# ADR-002: Composite view for shared hypothesis trees

## Status

Accepted (2026-07-03); merge key updated 2026-07-16

## Context

Several code repositories can contribute different hypothesis branches under the
same research problem (e.g. diversity bonus in `verl-agent-craftext` and external
operator in `TalkingHeads`). ResearchOS previously rendered one tree per project;
programs only grouped projects in the sidebar.

No single repository should be “dominant”: each repo owns its fragment of the tree
and syncs `koi-structure/` on its own orphan branch.

Independently created shared ancestors often reuse the same titles but get
different random node ids (`n-<uuid>`), so an id-only merge left duplicate
problem/cause vertices in the composite (and Hub auto-composite) view.

## Decision

1. **Grouping key:** optional frontmatter field `composite_id: <slug>` on
   `koi-structure/project.md`. Hub also auto-groups by normalized problem title
   when `composite_id` is absent (`auto-problem:<slug>`).
2. **Merge rule:** all discovered projects with the same `composite_id` (≥2 members)
   are merged at **read time**. Nodes match by structural signature
   `(node_type, normalize(title), canonical parent id)` — NFKC, casefold, collapsed
   whitespace. Same id still merges (legacy shared copies). On a signature hit,
   foreign ids remap onto the first member’s canonical id; child `parent_id` and
   board `owner_node_id` / card `linked_node_id` follow the remap. Same-title
   siblings inside one project stay distinct; only cross-project title matches
   collapse. Unique branches live in one repo each.
   **Hub grouping:** members are grouped by normalized **problem title** first.
   If any member has an explicit `composite_id`, that id is used as the public
   composite id (so a project with `llm-ood-decision-making` and another that only
   has the same problem text still form one composite, instead of splitting into
   `llm-ood-decision-making` vs `auto-problem:…`).
3. **API:**
   - `GET /composites` — list composite groups
   - `GET /composites/{composite_id}` — merged tree + boards + members + conflicts
4. **UI:** program sidebar shows a virtual entry (⎇ title) above member projects;
   opening it loads the composite view. Writes route to the owning repo via
   `node.project_id` / `board.source_project_id`.
5. **Conflicts:** if shared nodes differ across repos after a match (description on
   signature merge; title/parent/type/description on same-id merge), API returns a
   `conflicts` array; first member wins for display.

## Format example

```yaml
---
id: talking-heads
composite_id: llm-ood-decision-making
programs:
  - id: multimodal-reinforcement-learning
---
```

Each member repo includes shared nodes plus its own remediation/method subtrees.
Shared ancestors no longer need identical ids — matching titles under the same
parent are enough — though keeping shared ids remains the cleanest write path.

## Consequences

- Storage stays per-repo; composite is a view layer only (ResearchOS and Hub both
  call `koi.projects.composites.build_composite`).
- Renaming a shared node in one repo breaks the signature match until the other
  repos rename too (appears as a fork, not a silent merge).
- `PUT /projects/{id}` unchanged; composite id is not a writable project id.
- Literature / agent chat in composite view use the first member project (MVP).
- Future: broadcast PATCH for shared nodes; hide member projects when composite exists.

## References

- `koi/projects/composites.py`
- `hub/app/hub_composite.py`
- `api/routers/composites.py`
- `ReseachOS/web/app.js` — composite sidebar + write routing
