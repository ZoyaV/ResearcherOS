# Decision tree for grilling an experiment

This is an agent reference for common branch questions. Ask **one** question
from the current branch per turn and always include a recommendation.

## A — Context and claim

| # | Question template | Depends on |
|---|-------------------|------------|
| A1 | Which cause node `c-…` owns the card? | project.md |
| A2 | One-sentence claim: X **increases/decreases** Y under Z? | A1 |
| A3 | Why does this matter in the hypothesis tree (1–2 sentences for Section 1)? | A2 |
| A4 | Which KNOWLEDGE/research.json insight motivates the prediction? | A3 |

Red flags: “study the effect,” “see what happens,” or no direction of effect.

## B — Metric and verdict (Section 2)

| # | Question | Depends on |
|---|----------|------------|
| B1 | What single primary metric defines the final test? | A2 |
| B2 | How is it aggregated (mean/median/@k and across which seeds)? | B1 |
| B3 | What is the comparison baseline? | B1 |
| B4 | The claim is **supported** if which numeric threshold is met? | B1–B3 |
| B5 | It is **refuted** if what occurs? | B4 |
| B6 | It remains **open** under what data/noise conditions? | B4 |

Fix thresholds **before** the run; see `hypothesis-spec.md` and AGENTS.md.

## C — Boundaries and dependencies

| # | Question | Depends on |
|---|----------|------------|
| C1 | What does this run **not** establish (2–4 points)? | A2 |
| C2 | Which kanban cards `kb-…` block it? | project.md |
| C3 | What threatens validity (seeds, warm-up, leakage)? | D |

## D — Implementation (Section 3)

| # | Question | Depends on |
|---|----------|------------|
| D1 | How many runs (Sections 3.1, 3.2, …)? | B, C |
| D2 | Data: public name, N, filter, and local path? | D1 |
| D3 | Model/config and difference from the previous run? | D2 |
| D4 | Exact launch command or script? | D3 |
| D5 | Budget: epochs, steps, wall-clock, and seed count? | D4 |
| D6 | Where are metrics and logs written (`live_log`, jsonl)? | D4 |

When the repository already contains a command, show it and ask what to retain
or change.

## E — Tables and plots (Sections 4.1 / 5.1)

| # | Question | Depends on |
|---|----------|------------|
| E1 | Table A for the final Section 2 protocol: rows and columns? | B |
| E2 | Diagnostic tables B/C, explicitly not the final test? | E1 |
| E3 | Which plots (learning curve, ablation bar, etc.)? | B, D |
| E4 | Artifact format (PNG under `assets/`, `metrics_dir`)? | E3 |

A Section 3 task must point to an output, for example “→ Table A in Section 4.1”
or “→ Figure 1.”

## F — Tasks and card completion

| # | Question | Depends on |
|---|----------|------------|
| F1 | SMART tasks for Section 3.1 (action + object + criterion)? | D, E |
| F2 | Is Section 3.2 needed for a second scale or ablation? | D1 |
| F3 | Section 3.3 verifiable check → result checklist? | B4–B6 |
| F4 | Which checkpoint is passed to the next card? | F3 |

Example: “On dev-500, evaluate mean diversity over three seeds → JSON summary →
Section 4.1 Table A.”

## G — Kanban

| # | Question | Depends on |
|---|----------|------------|
| G1 | Short card title for project.md? | A2 |
| G2 | Board / method id in project.md? | G1 |
| G3 | Is the default `backlog` column correct? | G2 |

After G, summarize and draft the report. Write to the repository only when the
user requests it.
