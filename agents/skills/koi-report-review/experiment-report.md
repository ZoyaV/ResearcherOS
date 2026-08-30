# Experiment run report (working copy)

This is the deliverable of the AGENT that ran the experiment. Complete it
immediately after the run, one file per kanban card. It serves two purposes, so
the format is strict:

1. a human or review agent turns it into a public `.md` report in
   `projects/<id>/reports/<node>/<card>.md` using `report-skeleton.md`;
2. the reviewer uses its Knowledge base submission to decide **how** the result
   enters the knowledge base (see the matrix in `docs/research-workflow.md`).

This working report therefore contains operational details such as paths, raw
metrics, and commands. The public report replaces them with public names. Save
the file beside the public report; the recommended name is
`projects/<id>/reports/<node>/<card>.run.md` (`.run` denotes the working layer).

> Every line beginning with `>` is guidance; remove it when completing the report.

## 0. References

| Field | Value |
|------|----------|
| Hypothesis (cause) | `c-…` — short name |
| Method / card | `m-…` / `…` |
| Hypothesis specification | completed BEFORE the run: yes/no |
| Run date | YYYY-MM-DD |
| Run owner | model/person |
| Run status | completed successfully / failed / partial |
| Compute cost (optional) | `wall_h=…; gpu_h=…; n_gpus=…` — repeat as `compute_cost:` in the public report header |

> Optional in the `.md` report header (not in the table):
> `compute_cost: wall_h=2.4; gpu_h=4.8; n_gpus=2; until=SMA SR≥0.8; source=measured`
> Omit this line when the work used no GPU or training run.

## 1. What was run (reproducibility)

> Record exact run facts. Local paths and commands belong here and must not be
> copied into the public report.

- Command: `<exact launch command>`
- Runs in this card: N (list identifiers)
- Environment/hardware: `<runtime, versions, hardware, commit>`
- Raw metrics: `<artifact path>`
- Logs: `<log path>`

## 2. Primary metric and results

> Use the same metric as the specification's decision rule. The table contains
> raw numbers from jsonl. For multiple runs (sweep or seeds), use one row per run.

| run | conditions | seed | budget | primary metric | time | other |
|-----|------------|------|--------|----------------|------|-------|
| … | … | … | … | … | … | … |

One-sentence summary: …

## 3. Decision-rule evaluation

> Copy the rule from the specification verbatim and substitute the measured
> values. This connects evidence to the verdict: the verdict must follow from
> this substitution, not from a general impression.

- Rule (from the specification): supported if …; refuted if …; open if …
- Observation: metric = value (threshold = value)
- → the rule yields: **supported / refuted / open**

## 4. Threats and caveats (what this run does NOT establish)

> Give 2–4 items. Typical examples include seed variance (an effect within the
> variance is not robust), warm-up/cache effects (`scene_creation_s` on a cold
> start is a one-time cost and not training throughput), and metric ceilings
> (`success_rate=1.0` on a short budget cannot distinguish variants; measure
> reward or position_error).

- …

## 5. Knowledge base submission

> This is the agent's PROPOSAL for what to record and how. The reviewer decides
> using the matrix in `docs/research-workflow.md` and may accept it, lower its
> certainty, split it, reject it, or retain only a methodological insight.

### 5.1 Proposed cause-node verdict

- `c-…` → **open | supported | refuted**
- rationale (one line referring to Section 3): …

### 5.2 Proposed insights (at most 3 per method; research.json format)

> These fields are ready for `research.json`. `narrative` is the readable UI
> answer and `answer` is the technical summary. Use `certainty=definite` ONLY
> when the threshold is exceeded by a clear margin and the conclusion is robust
> to the caveats in Section 4; otherwise use `tentative`.

```json
[
  {
    "method_id": "m-…",
    "card_id": "…",
    "question": "What question does this run answer?",
    "answer": "concise technical summary with measured values",
    "narrative": "readable answer for the UI",
    "certainty": "definite | tentative",
    "importance": 3
  }
]
```

### 5.3 Recommended integration form

> Choose one option from the decision matrix in `docs/research-workflow.md` and
> explain why in one line: accept as written / accept after lowering to
> tentative+open / split into N insights / reject (methodological error; rerun) /
> methodological insight only.

- Recommendation: …
- Reason: …
