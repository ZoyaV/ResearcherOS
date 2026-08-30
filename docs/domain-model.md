# KOI domain model

## Reasoning flow (science agile)

```
Problem
    ↓ “why does this happen?”
Cause (explanatory hypothesis)
    ├→ Cause evidence          ──→  Method(s) ──→  [Kanban] ──→ Experiments
    └→ Remediation hypothesis  ──→  Method(s) ──→  [Kanban] ──→ Experiments
```

Unlike conventional Agile (epic → story → task), this model has no “features.” Each node receives a **verdict**: the hypothesis is open, supported by data, or refuted.

## Tree rules

| Parent | Allowed children |
|----------|-----------------|
| — (project root) | Problem |
| Problem | Cause |
| Cause | Cause evidence, Remediation hypothesis |
| Evidence / Remediation | Method |
| Method | — (experiments live on the kanban board) |

## Kanban

- Attached to a `method` node (a way to test a hypothesis); one hypothesis may have several methods.
- Created automatically when a `method` node is added.
- Cards represent planned or running experiments. They do not have to duplicate an Experiment node in the tree; linkage is optional through `linked_node_id`.
- Default columns: Backlog → Planned → Running → Done.

## Hypothesis states (`verdict`)

- `open` — in progress
- `supported` — supported by data
- `refuted` — refuted

In the prototype, verdicts are defined in the model; a UI for changing them is the next step.
