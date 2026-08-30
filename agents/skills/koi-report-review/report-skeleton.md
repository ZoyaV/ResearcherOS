# <Card title exactly as shown on the kanban board>

> HOW-TO (header): Keep Status synchronized with the kanban column (backlog →
> running → done). If the card is not done, add one line describing what blocks
> completion. Do not use bold; see [report-rules.md](report-rules.md). After a
> GPU/training run, optionally add
> `compute_cost: wall_h=2.4; gpu_h=4.8; n_gpus=2; until=SMA SR≥0.8` (shown as a
> kanban chip). Omit it for analysis or literature work.

Status: planned
Kanban: `kb-…`
Dependencies: `kb-…` (…) → this card → `kb-…`

---

## 1. Experiment description and rationale

> HOW-TO: Explain why first, then measurement (Section 2), plan (Section 3), and
> runs (Sections 4+). Write in the team's voice and in paper-ready prose: no
> `*.json` or local paths, only public names (see
> [no-ai-report-rules.md](../no-ai-report-rules.md)). Do not mix in metrics.

Goal: …

> HOW-TO (goal): State one measurable change (for example, `mean diversity ≥
> 1.78`), not the name of an activity such as “run SFT.”

Role in the hypothesis: …

> HOW-TO (hypothesis): In 1–2 sentences, name the tree node and what this card
> passes to `kb-…`.

Out of scope: …

> HOW-TO (boundaries): Give 2–4 points describing what this run does not establish.

---

## 2. Primary metric (final test)

> HOW-TO: Define one primary criterion for moving the card to done. Explicitly
> list what is excluded from the final test.

### Definition

| Parameter | Value |
|-----------|-------|
| Metric | … |
| Aggregation | … |
| Protocol | public dataset names, N, temperature, seed |
| Baseline | base / previous checkpoint |
| Script / artifacts | paths to logs, jsonl, summary |

> HOW-TO (Section 2): Use paper-facing names in prose and Protocol. Put paths only
> in Script / artifacts or Section 3.

---

## 3. Setup and preparation

> HOW-TO: Setup, TODO items, and collection belong only in Section 3. Every
> Section 4/5 run needs a corresponding Section 3.x with Tasks. Make each line as
> SMART as practical but concise: action + object + completion artifact/table/
> Section N.2. See
> [no-ai-report-rules.md](../no-ai-report-rules.md#subtasks-smart-and-concise).
> Do not write interpretations or vague goals such as “improve the model.”

### 3.1 <Scale or variant A> → Section 4

> HOW-TO: Use a meaningful `###` title such as “mini-pilot on failures,” not a
> file slug. Introduce public names here; if none exist, create them or ask the
> author.

Summary: …

- Data used: <public dataset name> — description; local `path.json`, N items, pool/filter
- Model used: `Qwen/…`, LoRA rank, epochs
- Training / script: `run_….sh`, run id `…-20260520-…`
- Difference from the previous run: one line
- Status: planned → [Section 4](#4-experiment-1--short-descriptive-name)

Tasks:

- [ ] On <public dataset name>, <what to measure/generate and with what N or epoch count> → numeric artifact (local: `run_….sh`, `….json`)
- [ ] In [Section 4.1](#41-results), table A — <rows/columns>; table B if needed (Section 2 protocol)
- [ ] In [Section 4.2](#42-conclusions), answer <question addressed by this run>, without comparing another run if that comparison belongs in Section 5
- [ ] _(if needed)_ After [Section 3.2](#32-), provide an aggregate comparison in Section 5.1

#### Data collection

> HOW-TO: Describe collection, augmentation, and training volume with numbers, or
> state “no collection; …”. Put `json`/`parquet` paths here. Do not mix in
> checkpoint-quality tables; those belong in Section 4.1.

…

```bash
# launch / collection commands, when reproducible
```

### 3.2 <Scale or variant B> → Section 5 _(optional)_

> HOW-TO: Every Section 3.x must include the fields, Tasks, and Data collection —
> not only the first run.

Summary: …

- Data used: …
- Model used: …
- Training / script: …
- Difference from Section 3.1: …
- Status: planned → [Section 5](#5-experiment-2--short-descriptive-name)

Tasks:

- [ ] … _(self-contained description; add local context in parentheses at the end)_
- [ ] In [Section 5.1](#51-results), specify tables and comparisons; in [Section 5.2](#52-conclusions), answer the card question from Section 1

#### Data collection

…

```bash
# when needed
```

### 3.3 Card completion criterion

> HOW-TO: Provide a verifiable checklist and a check → result table. State which
> checkpoint proceeds to the next card.

| Check | Result |
|-------|--------|
| … | _(after the run)_ |

---

## 4. Experiment 1 — <short descriptive name>

> HOW-TO: This section contains only run results and conclusions. Setup and data
> collection belong in [Section 3.1](#31-scale-or-variant-a--section-4). The `##`
> heading must not contain a dataset slug or run id.

### 4.1 Results

> HOW-TO: Do not place conclusions between tables. Table A is the final Section 2
> protocol; B and C are diagnostics. Protocol uses public names, not files. Put
> artifact paths at the end of the subsection.

#### Table A. …

Protocol: Section 2, …

| model | mean | … |
|-------|------|---|

#### Table B. … _(diagnostic, optional)_

Protocol: … ; not the final test.

| … | … |

Artifacts: `…`

### 4.2 Conclusions

> HOW-TO: Write paper-ready prose: “Table A/B/C shows …” followed by an overall
> conclusion. Include run status and `global_step_…` for the kanban.

From Table A: …

Overall conclusion: …

Run status: … Checkpoint for the next step: `global_step_…`

---

## 5. Experiment 2 — <short descriptive name> _(optional)_

> HOW-TO: Setup and collection are in Section 3.2; this section contains only
> Section 5.1 Results and Section 5.2 Conclusions.

### 5.1 Results

_(after the run: table A, then diagnostics)_

### 5.2 Conclusions

_(after the run)_

---

## Appendix _(optional)_

> HOW-TO: Put raw tables, per-prompt jsonl, and full paths here. Sections 4.1 and
> 5.1 contain aggregate results.

<details>
<summary>Detailed / raw tables</summary>

…

</details>
