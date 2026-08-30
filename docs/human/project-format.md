# KOI project file format (`project.md`)

Projects are stored in `projects/<project-id>/project.md`. The format is designed for reading and editing by humans and AI agents.

## Frontmatter (YAML)

```yaml
---
id: demo-aggregation
title: Project title
description: Brief description (optional)
updated: 2026-05-20T12:00:00Z
format: koi/1
---
```

## Hypothesis tree

Nodes are represented by Markdown headings. The number of `#` characters gives the tree depth.

```markdown
# problem: n-problem

Problem title (the first non-empty line after the heading)

Problem description (subsequent lines until the next heading or kanban board).

## cause: n-cause-misfold

Cause: aggregation due to misfolding

### cause_evidence: n-ev-fold

Evidence: ThT fluorescence
```

Node types: `problem`, `cause`, `cause_evidence`, `remediation`, `method`, and legacy `experiment`.

Optionally, immediately after a heading:

```markdown
verdict: supported
```

Values: `open`, `supported`, `refuted`.

## Experiment kanban

Only `method` nodes have kanban boards. Place a Markdown table immediately after the method text:

```markdown
#### method: m-ev-fold

ThT and TEM

Method description…
```

```markdown
<!-- koi:kanban board-ev-fold -->
| backlog | running | done | successful |
| --- | --- | --- | --- |
| Inclusion TEM <!-- id:c2 desc:n=3 replicates --> | ThT time course <!-- id:c1 --> | |
```

- Board name in the comment: `board-<node-id>` or a custom name.
- Column headings are lowercase Latin column IDs: `backlog`, `running`, `done`, and optionally `successful` after `done`.
- Cells contain card text; metadata lives in an HTML comment: `<!-- id:... created:... updated:... desc:... tags:... deps:... -->`.
- `created:` / `updated:` are optional ISO-8601 UTC timestamps (`2026-08-07T08:18:00Z`) set by the system when a card is created or edited.
- `tags:` is an optional comma-separated list using Latin letters, digits, `-`, and `_`; for example, `tags:gpu,sft,ablation`.
- `deps:` optionally lists prerequisite card IDs separated by commas; for example, `deps:seg-pareto-groups,seg-targeting`. Cards without `deps` appear independently in DAG view.
- An optional `card_tags: [gpu, baseline, ...]` frontmatter field provides the project tag vocabulary for UI suggestions.

## Method research questions

Questions and answers from completed experiments are **not** stored in `project.md`. They live in:

```
projects/<project-id>/research.json
```

Format:

```json
{
  "version": 1,
  "questions": [
    {
      "id": "rq-sft-diversity",
      "method_id": "m-n-rem-pretrain",
      "card_id": "kb-sft",
      "question": "…",
      "answer": "brief technical summary",
      "narrative": "human-readable answer for the UI",
      "certainty": "definite",
      "importance": 5
    }
  ]
}
```

- `method_id` — ID of a `method` node in the tree.
- `card_id` — ID of the source kanban card.
- `certainty`: `definite` | `tentative`.
- `importance`: 1–5.
- No more than **three** questions per method.

When a project loads, the API reads `research.json` and attaches questions to method nodes. Saving through the UI or PATCH writes them back to `research.json`. Legacy `<!-- koi:method-questions -->` blocks in `project.md` migrate automatically on first load.

## Tree rules

| Parent | Children |
|----------|------|
| — | problem |
| problem | cause |
| cause | cause_evidence, remediation |
| cause_evidence, remediation | experiment |

## Example for an agent

1. Read `projects/<id>/project.md`.
2. Add a node as a new heading at the appropriate depth below its parent.
3. For evidence/remediation, add a `<!-- koi:kanban ... -->` block and table.
4. Save the file. On startup, the API picks up changes when the project reloads; alternatively, use PUT through the API.

## Kanban-card reports

Detailed reports are stored separately from `project.md`:

```
projects/<project-id>/reports/
  index.json                    # card_id → path relative to reports/
  Hypothesis_title/             # directory = kanban node title (hypothesis or evidence)
    Card_title.md
```

- The filename is derived from the **card title**: spaces become `_`, all other text is preserved except path-invalid characters.
- Name collisions receive `_2`, `_3`, and subsequent suffixes.
- Renaming a card renames its file; deleting a card deletes the file.
- When a project loads or a card is added, an empty `.md` is automatically created for **every** kanban task if one does not exist.
- API: `GET/PUT /projects/{id}/boards/{board_id}/cards/{card_id}/report` (PUT body: `{ "content": "..." }`).

### Report content

Complete formatting rules are part of **[koi-report-review](../../agents/skills/koi-report-review/)**:

| File | Topic |
|------|------|
| [report-skeleton.md](../../agents/skills/koi-report-review/report-skeleton.md) | §§1–N template with HOW-TODO under each section |
| [report-rules.md](../../agents/skills/koi-report-review/report-rules.md) | Do/don't rules and formatting without “AI Markdown” |

In brief: header → **why** (§1) → **metric** (§2) → **setup and collection** (§3) → for each run in §4+: **results** and **conclusions**, without repeating the §3 setup.

After a GPU/training run, the header may optionally include a cost line; the UI shows it as a kanban-card chip and report-corner badge:

```text
compute_cost: wall_h=2.4; gpu_h=4.8; n_gpus=2; until=SMA SR≥0.8; source=measured
```

`source=recovered` means recovered from old logs. Do not add this line for analysis/literature work without training.

After a GPU/training run, the header may optionally include a cost line; the UI shows it as a kanban-card chip and report-corner badge:

```text
compute_cost: wall_h=2.4; gpu_h=4.8; n_gpus=2; until=SMA SR≥0.8; source=measured
```

`source=recovered` means recovered from old logs. Do not add this line for analysis/literature work without training.

Examples of a final test (also see the style rules):

- **SFT:** a consistent diversity metric on **train** and **test** for LoRA checkpoints (base vs. adapter); an intermediate probe on `fork_prompts.json` is not a final test.
- **RL (closing a hypothesis):** an SR table for BASE, pre-RL SFT, BASE+RL, and SFT+RL; at minimum, `SR(SFT+RL) > SR(BASE+RL)`.

Reference report in the repository: `projects/ai-agents-embodied/reports/.../Run_SFT_training_on_dataset.md`.
