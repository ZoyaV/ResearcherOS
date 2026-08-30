---
name: koi-grill-experiment
description: >-
  Relentless one-question-at-a-time interview to design a new KOI experiment
  before any run: hypothesis, setup, implementation, plots/tables, and done
  criteria, with a recommended answer on every turn. Use when the user asks for
  a new experiment, kanban card, hypothesis, experiment setup, or says “grill,”
  “pressure-test the plan,” or “design the experiment.”
---

# KOI: grill an experiment

This interview follows [grill-me](https://www.aihero.dev/skills-grill-me) by
Matt Pocock: do not accept a rough idea; **push the setup to shared
understanding** before a run, moving a card to done, or editing code.

This is **planning**, not execution. The output is a draft report covering
Sections 1–3 (or `hypothesis-spec.md`) and a kanban card. Use
**koi-execute-card** for the actual run.

## When to run

1. A new experiment, card, or hypothesis starting from scratch or one sentence.
2. The user asks to design or pressure-test a setup that lacks a Section 2
   metric, tasks, or threshold.
3. Before **koi-report-review** when Sections 1–3 are still vague.
4. The user explicitly requests a grill or one-question-at-a-time interview.

Do not run it when a card is already `running` or `done` and only execution is
needed; use **koi-execute-card**.

## Interview rules

1. **One question per turn.** Never send a list of 5–20 questions.
2. Give a **recommended answer** to every question: a position and one sentence
   explaining why. The user may accept, correct, or choose another option.
3. **Inspect code and project first.** Read `project.md`, `KNOWLEDGE.md`,
   `research.json`, nearby reports, and scripts instead of asking what the
   repository already shows. State the finding and ask for confirmation.
4. Explore the decision tree depth-first. Close one branch before another and
   ask dependency parents before children (metric ← claim ← hypothesis node).
5. Do not start the run or move the card to `running` until branches A–G are
   closed, or explicitly recorded open with a reason.
6. Push back on unfalsifiable claims, post-hoc thresholds, and missing controls;
   recommend a concrete repair.

Turn format:

```text
Q[i]/[~N]: <question>

Recommendation: <answer> — <brief rationale>.

(Or: I inspected <file/report> and found <finding>. Confirm?)
```

Wait for the user's answer. Do not include Q[i+1] in the same message.

## Required decision branches

Follow dependency order; see [experiment-tree.md](experiment-tree.md).

| Branch | Topic | Artifact destination |
|--------|-------|----------------------|
| **A** | Context: project, cause node, claim, rationale | Section 1, `hypothesis-spec.md` |
| **B** | Primary metric and supported/refuted/open rule | Section 2, `.run.md` Section 5.2 |
| **C** | Boundaries and kanban dependencies | Section 1, report header |
| **D** | Implementation: data, model, command, budget, seeds | Section 3.x, Data collection |
| **E** | Tables and plots for Sections 4.1/5.1 | Section 3 tasks and table titles |
| **F** | SMART tasks and card completion criterion | Section 3 Tasks and 3.3 |
| **G** | Kanban card id, board, and `backlog` column | `project.md` |

Skip a branch only when the user explicitly says it is unnecessary; record the
skip in the final summary.

## Start the session

1. Determine `project_id` from cwd or `projects/`, or ask one question.
2. Read `koi-structure/project.md`, `KNOWLEDGE.md`, and `research.json` to learn
   what is known about the method and adjacent cards.
3. Summarize the context in 2–4 sentences.
4. Ask Q1 from branch A or the most blocking uncertainty.

If the user only says “I want to test X,” ask first for the directional claim,
not a vague request to study X.

## End the session

When all required branches are closed, provide **without further questions**:

1. A decision-summary table: decision → recorded value.
2. Draft artifacts, not final files unless the user asked to write:
   - Sections 1–3 following
     [`../koi-report-review/report-skeleton.md`](../koi-report-review/report-skeleton.md),
     or a completed
     [`../koi-execute-card/hypothesis-spec.md`](../koi-execute-card/hypothesis-spec.md);
   - table/plot inventory: name → rows/columns → protocol;
   - Section 2 supported/refuted/open thresholds fixed **before the run**.
3. Explicit next steps:
   - write the report and create the card in `backlog`;
   - run **koi-report-review** critics 1–3 on Sections 1–3;
   - run **koi-prose-style** on the card title and Section 1 when prose is rough.

Do not move the card to `running`; **koi-execute-card** does that when execution
begins.

## Checklist before writing to the repository

When the user asks to write or create the card, verify:

- [ ] Claim is falsifiable and directional
- [ ] Section 2 has one primary metric and supported/refuted/open thresholds
- [ ] Every Section 3 run has Tasks with artifact/Section N completion criteria
- [ ] Section 4.1 tables are named A/B/etc.; plots have a path or `metrics_dir`
- [ ] Kanban dependencies appear in the report header
- [ ] Card is in `backlog`, not `running`

After writing, run **koi-report-review** for setup with critics 1+2+3 in parallel.

## Related skills

- **koi-report-review** — Sections 1–3 quality after the grill
- **koi-execute-card** — execution, Section 3 checkboxes, `running` → `done`
- **koi-prose-style** — readable claim and Section 1 prose
- **koi-done-research** — only after done, never during planning

## Origin

Matt Pocock's minimal prompt says to interview relentlessly, ask one question at
a time, recommend an answer, and inspect the codebase first. This skill keeps
that discipline and maps the branches to KOI reports, hypotheses, and kanban.
