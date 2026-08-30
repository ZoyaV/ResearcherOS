---
name: koi-execute-card
description: >-
  Execute a KOI/ResearchOS kanban card in strict order: (1) move to running
  immediately before any other work, (2) mark Section 3 Tasks [x] as each item
  completes, and (3) move to done when finished. Use when the user asks to run,
  execute, or check a kanban/experiment card, with
  `koi.projects.report_ingest.cli`, or says “execute the card.”
---

# KOI: execute a kanban card

Executing an experiment card is not a one-off code edit. It requires following
the report and card status, maintaining the task checklist, and synchronizing
the kanban column.

## Three mandatory steps (keep this order)

1. **Start:** move `backlog` → **`running`** immediately after locating the card,
   before reading the report/code or running the experiment.
2. **During work:** after each completed task, change `- [ ]` → `- [x]` in
   Section 3 and **save** the report immediately.
3. **Finish:** move `running` → **`done`** when every task is checked and
   Sections 4/5 are complete, before replying to the user and before
   **koi-done-research**.

## When to run

1. The user asks to execute/check/do a card by id or title.
2. Before `python -m koi.projects.report_ingest.cli <project> <card>`.
3. A card is already running but its report tasks are not checked.
4. The user refers to a specific experiment on a method's kanban.

Use **koi-execute-card** first for progress and kanban, then
**koi-done-research** after moving to done to record the research conclusion.

## Primary rule

Synchronize kanban in `project.md` and the report **as the work happens**:

1. First action: if the card is in `backlog`, move it to `running` before
   editing reports, code, or data.
2. Last action: when all tasks are `[x]` and Sections 4/5 are complete, move it
   to `done` before replying and before koi-done-research.

A completed report with a card still in backlog is invalid.

## Start: card context

1. Find the card in the project's `koi-structure/project.md`
   (`<!-- koi:kanban … -->` table), at
   `projects/<id>/koi-structure/project.md`, or through the API.
2. If it is in backlog, **immediately** move it to running and save. Only then
   continue.
3. Resolve the report path:

```bash
curl -s "http://127.0.0.1:8010/projects/<project_id>/boards/<board_id>/cards/<card_id>/report-path"
```

Or locate it on disk at
`projects/<id>/koi-structure/reports/<method>/<card>.md` using
`reports/index.json`.

4. Read the complete report: Sections 1–2 (goal/metric), Section 3 Tasks
   (`- [ ]` / `- [x]`), and existing Section 4+ results.

If the report is empty, copy `../koi-report-review/report-skeleton.md`, fill
Sections 1–3, run **koi-report-review** critics 1–3, then continue execution.

## Task rule (mandatory)

Tasks live **only in Section 3** under `Tasks:`:

```markdown
Tasks:

- [ ] Action + object + completion criterion → artifact / Section N.1 / N.2
- [x] Already complete — the criterion on this line is satisfied
```

| Moment | Agent action |
|--------|--------------|
| Card is taken into work | Immediately move `backlog` → `running` in `project.md` or API |
| A task's criterion is met | Immediately change `[ ]` → `[x]` and save the report |
| All tasks `[x]`, Section 2 resolved, Sections 4/5 filled | Immediately move `running` → `done`, then run koi-done-research |
| Task not completed | Leave `[ ]`; write “not completed because …” in Section 4 |

Never check work in advance and never move to done while Section 3 has
unexplained incomplete items. A checkbox means the SMART criterion on the same
line is met; see `../koi-report-review/report-rules.md`.

## Kanban columns

| Column | Meaning |
|--------|---------|
| `backlog` | Not started |
| `running` | Work is in progress; report or experiment started |
| `done` | Tasks checked, report has results/conclusions, and Section 2 is resolved or explicitly open/abandoned |

### Move the card

Through the API on port 8010:

```bash
curl -s -X PATCH "http://127.0.0.1:8010/projects/<project_id>/boards/<board_id>/cards/<card_id>" \
  -H "Content-Type: application/json" \
  -d '{"column_id": "running"}'
```

Use `{"column_id": "done"}` to finish. Moving to done fills the
done-research queue.

Without the API, move the card row to the appropriate cell in the
`backlog | running | done` table in `koi-structure/project.md` and save
immediately.

## Live panel in the UI

While a card is running, the method map shows a live inspector. The UI reads
files from disk; the agent curates the displayed fields. Add optional lines to
the card description or report header:

```text
live_log: projectcode/runs/train.log
metrics_dir: projectcode/runs/plots
live_note: epoch 3, loss 0.38
compute_cost: wall_h=2.4; gpu_h=4.8; n_gpus=2; until=SMA SR≥0.8; source=measured
```

Paths are relative to the project repository root (`code_root` in project.md)
or its sibling experiment-code directory.

| Moment | Update |
|--------|--------|
| Start remote job | Point `live_log:` at the tailed log; add one-line `live_note:`; write ISO `started_at` + `n_gpus` to job state |
| Milestone/error | Update `live_note:` and/or check a completed task |
| Plots appear | Set `metrics_dir:` or copy PNG files to `reports/.../assets/` |
| GPU/training job finishes | Calculate wall/GPU hours and optionally add `compute_cost:` |
| Card finishes | Move to done; live fields may be removed; retain `compute_cost:` |

Do not duplicate all stderr; provide meaningful updates only.

### Optional `compute_cost:`

Do not add this line for analysis, literature, or non-training cards. The UI
shows a kanban chip and report badge only when it exists.

```text
compute_cost: wall_h=<hours>; gpu_h=<hours>; n_gpus=<N>; until=<milestone>; source=measured|estimated|recovered
```

At least `wall_h` or `gpu_h` is required; all other keys are optional.

- `wall_h`: elapsed hours for the measured segment
- `gpu_h`: usually `wall_h × n_gpus` for exclusive GPUs, otherwise measured use
- `until`: milestone such as `SMA SR≥0.8` or `budget 300 updates`
- `source=recovered`: reconstructed from logs; `estimated`: rough estimate

Write `started_at` in ISO UTC and `n_gpus` to log/state at launch. At completion,
use `finished_at` or the threshold timestamp to fill `compute_cost:`.

## One-card workflow

```text
1. Find card in project.md (id, board, column)
2. BLOCKING: backlog → running immediately, before step 3
3. Read report and card description
4. For every Section 3 task:
     do work → immediately [x] → save report
5. Fill Sections 4/5 or .run.md for ingest
6. Run koi-report-review critic 4 on results
7. BLOCKING: running → done after full checklist and report
8. Run koi-done-research
9. Run koi-project-sync when needed
```

### Save the report

Edit `koi-structure/reports/.../*.md` directly, or use:

```bash
curl -s -X PUT "http://127.0.0.1:8010/projects/<project_id>/boards/<board_id>/cards/<card_id>/report" \
  -H "Content-Type: application/json" \
  -d '{"content": "<complete report Markdown>"}'
```

Save after every meaningful change. The UI report preview then shows current
checkboxes and results.

### Ingest a hypothesis

For automatic knowledge integration:

```bash
python -m koi.projects.report_ingest.cli <project_id> <card_id>
# or after a manual .run.md:
python -m koi.projects.report_ingest.cli <project_id> <card_id> --ingest-only
```

Ingest moves the card to done itself, but public-report tasks must already be
`[x]` so report and kanban do not diverge.

## Checklist before replying

- [ ] Card moved to `running` at the beginning if it started in backlog
- [ ] Every completed Section 3 task is `[x]`
- [ ] Report is saved through file or API
- [ ] Kanban column in `project.md` matches reality
- [ ] At done, **koi-done-research** has run or is scheduled

## Long or remote experiments

For “systematic research,” “autoresearch,” or Manager/Researcher/Debugger roles,
use **koi-card-autoresearch**. Kanban, Section 3, and report still follow this
skill.

Also inspect project-specific skills under `/.cursor/skills/` in the project
root for job, sysmon, or remote scripts, such as `verl-experiment-run`.

## Related skills

- **koi-card-autoresearch** — long Manager / Researcher / Debugger runs
- **koi-report-review** — report and task quality
- **koi-done-research** — question/narrative after done
- **koi-prose-style** — readable report prose
- **koi-project-sync** — commit/push project changes
