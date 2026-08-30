---
name: koi-report-review
description: >-
  Review KOI experiment reports with four readonly subagent critics before
  saving: (1) prose style, (2) setup clarity and dependencies, (3) SMART
  subtasks in Section 3, and (4) results completeness and readable conclusions.
  Use when drafting or editing public reports (report-skeleton), experiment
  setup Sections 1–3, or results Section 4+; also use for .run.md after a run.
  Always sync kanban in project.md: backlog → running when starting a card,
  running → done when the report is complete.
---

# KOI: report review with four critics

A public report lives at `projects/<id>/reports/<node>/<card>.md` and follows
[`report-skeleton.md`](report-skeleton.md) and
[`report-rules.md`](report-rules.md). The working layer is `*.run.md` and follows
[`experiment-report.md`](experiment-report.md).

Before writing the file, run a **team of four read-only subagents**. The primary
agent orchestrates: draft → critics → rewrite → repeat until PASS.

| Critic | When | Sections |
|--------|------|----------|
| **1 — Style** | setup | Section 1, Section 2 prose, Section 3 headings, header |
| **2 — Setup** | setup | Sections 1–3: dependencies, data, metrics |
| **3 — Tasks** | setup | Section 3 Tasks (`- [ ]`) |
| **4 — Results** | after the run | Section 3.3, Section 4+, Section 5+; Sections 2–5 for `.run.md` |

During the **setup phase** (writing or editing Sections 1–3), run critics
**1 + 2 + 3 in parallel**. During the **results phase** (writing or editing
Section 4+ or a post-run `.run.md`), run critic **4**. If the same edit changes
Section N.2 conclusions, also run critic **1** on Section N.2 in parallel with 4.

Write the file only after every critic required for the phase returns `PASS`.

Detailed prompts: [reviewers.md](reviewers.md). Critic 1 follows the same style
as `koi-prose-style`; use that skill for card/UI prose outside reports.

## Synchronize kanban in project.md (mandatory)

The report and kanban column must agree. **Do not start** editing the report
until the card is in **`running`**. **Do not end** a session with a completed
report while the card is not in **`done`**.

| Moment | Action |
|--------|--------|
| Start working on the card (**first action**, before Sections 1–3) | Move `backlog` → `running` in the `<!-- koi:kanban … -->` table in `koi-structure/project.md`, or PATCH `{"column_id": "running"}` |
| Report complete: all tasks `[x]`, Sections 4/5 filled (**last action**, before koi-done-research) | Move `running` → `done` in the same file or PATCH `{"column_id": "done"}` |

The kanban lives at `projects/<id>/koi-structure/project.md` or
`<repo>/koi-structure/project.md` in a discovery mount. Its columns are
`backlog | running | done | successful`: move the card row into the appropriate
cell and save. **`done`** means the report is complete and is the terminal state
for the agent and done-research. **`successful`** means the hypothesis has been
confirmed and is an optional manual step after `done`.

A common failure is completing a report while leaving its card in `backlog`.
Before replying to the user, open `project.md` and verify that the column matches
the actual state.

For Section 3 checkboxes and card moves, use **koi-execute-card**. After `done`,
use **koi-done-research**.

## When to run

0. Executing a kanban card — use **koi-execute-card** (move to `running` first,
   update Section 3 checkboxes, and move to `done` at the end).
1. Creating a new report from the skeleton and filling Sections 1–3.
2. Revising setup before a run: dependencies, tasks, and Section 2 metric.
3. Filling Sections 4+ / 5+ after an experiment.
4. Reviewing a working `.run.md` before ingest with
   `python -m koi.projects.report_ingest.cli --ingest-only`.
5. The user asks to review or critique a report.

## Prepare excerpts

Extract **only the relevant sections** from the draft, not the entire file.
Remove `> HOW-TO` blocks: critics evaluate content, not the template. State the
file type and phase:

```text
Report: projects/<id>/reports/<node>/<card>.md
Phase: setup | results | both
Card id: <kb-…>
---

<Sections 1–3 or Section 4+>
```

For `.run.md`, add `Type: run`. Critic 2 checks Section 1 reproducibility,
critic 3 is skipped because there are no Section 3 tasks, and critic 4 checks
Sections 2–5.

## Run critics (subagents)

Use these parameters for every subagent:

- `subagent_type`: `generalPurpose`
- `readonly`: `true`
- `run_in_background`: `false`

### Setup phase — three parallel subagents

Send one message with three Task calls:

| description | Prompt |
|-------------|--------|
| `Report critic 1 style` | Critic 1 prompt from [reviewers.md](reviewers.md) plus excerpts |
| `Report critic 2 setup` | Critic 2 prompt plus excerpts |
| `Report critic 3 SMART` | Critic 3 prompt plus excerpts |

### Results phase — one or two subagents

| description | Prompt |
|-------------|--------|
| `Report critic 4 results` | Critic 4 prompt plus excerpts **and** the corresponding Section 3.x promises |
| `Report critic 1 style` | Only when changing Section N.2 or `.run.md` Section 5.2 narrative |

Give critic 4 both what Section 3.x promised and what Sections N.1/N.2 contain.

## Combine verdicts

Every critic replies:

```text
Line 1: PASS or FAIL
If FAIL: table Location | Problem | Suggested fix
```

- All `PASS` → save.
- Any `FAIL` → combine the tables, rewrite the affected parts, and rerun only
  failed critics (or the whole phase for broad edits). Allow at most **3** rounds
  per phase.
- After a third `FAIL`, show the combined table to the user and do not save
  without approval.

Tell the user which phase was reviewed, which critics passed, and the number of
iterations.

## Orchestrator checklist

**Kanban (at start and finish)**

- [ ] The card is in `running` in `project.md` or the API before the first edit
- [ ] A completed report's card is in `done` after critic PASS and before replying

**Setup**

- [ ] Section 1 has a measurable goal, hypothesis rationale, boundaries, and no slugs in prose
- [ ] Section 2 defines one primary metric and protocol, separating artifacts from prose
- [ ] Every Section 3.x has data, model, script, difference, status, tasks, and collection
- [ ] Critics 1+2+3 return PASS

**Results**

- [ ] Section N.1 starts with Table A for the Section 2 protocol and contains no conclusions
- [ ] Section N.2 cites the tables and gives an overall conclusion in readable language
- [ ] Section 3.3 / done criterion is complete
- [ ] Critic 4 returns PASS (and critic 1 for Section N.2 when needed)

## Related material

- Template: [`report-skeleton.md`](report-skeleton.md)
- Rules: [`report-rules.md`](report-rules.md)
- Working report: [`experiment-report.md`](experiment-report.md)
- Cards/UI prose: `koi-prose-style`
- Ingest: `AGENTS.md` (format gates for Section 0, Section 5.1, and Section 5.2 JSON)
