# KOI style examples (good / bad)

Reference project: `bicycle_problem/koi-structure/project.md`.

## Nodes and descriptions

A map title has at most **8 words**. Details belong in the description.

| | Title | Description |
|---|-------|-------------|
| Good | Search budget is spent inefficiently | Broad, competitive queries consume search-ad budget while producing few useful actions. |
| Bad | Budget Waste in Search Campaigns | — |
| Bad | Inefficient budget waste in search campaigns | — |

| | Title | Description |
|---|-------|-------------|
| Good | Model fails to reproduce game rules | Given a recorded game, the world model does not reconstruct the moves and rules during validation. |
| Bad | The world model does not reproduce recorded game moves during validation | Entire explanation is overloaded into the title. |
| Bad | Executable code world model fails trace transitions | — |

| | Label | Note |
|---|-------|------|
| Good | Click share is about eleven percent | Description: mean click-through rate (CTR) is about 11%. |
| Bad | CTR ~11% | Bare abbreviation |
| Bad | Click-through rate equals 11% | Better than an abbreviation, but prefer a reader-facing claim |

## Kanban cards

Card titles have at most **8 words**; details and metrics belong in `desc`.

| | Title | desc |
|---|-------|------|
| Good | Summary table by display format | Four format/device combinations with impressions, clicks, click-through rate, and cost per click. |
| Bad | Summary table for text and image across phone and desktop traffic | Title is too long. |
| Bad | fmt-aggregate CTR/CPC table | aggregate by format×device |

| | Title | desc |
|---|-------|------|
| Good | Disable images on phones | New click-through rate, click count, and spend without mobile image ads. |
| Bad | What changes if we stop showing images on phones | Title is too long. |
| Bad | Simulate fmt-policy-off | mobile display off scenario |

## research.json (question / narrative)

| | Field | Text |
|---|-------|------|
| Good | question | Does training on example trajectories make the agent choose a wider variety of actions? |
| Bad | question | Does SFT improve action diversity vs baseline? |
| Good | narrative | Yes. In the same situation, the model considered about one and a half action variants before training and about two afterward. |
| Bad | narrative | mean diversity 2.02 vs 1.46 base (step 77) |
| Good | answer | mean diversity 2.02 vs 1.46 base (step 77) |

Technical abbreviations and raw numbers are allowed in `answer`.

## Methods and hypotheses

| | Text |
|---|------|
| Good | Test whether display format and device affect click-through rate |
| Bad | Validate format×device effect on CTR |
| Bad | A/B test: format device mismatch hypothesis |

| | Text |
|---|------|
| Good | For each segment, calculate impressions, clicks, click-through rate (CTR), spend, and cost per click (CPC). |
| Bad | Per segment: impressions, clicks, CTR, spend, CPC |

## AI-sounding tone

A cluster of markers in short UI text is bad. Repair with facts, not synonyms.

| | Text |
|---|------|
| Good | Disabling phone images increased click-through rate by two percentage points. |
| Bad | This groundbreaking solution marks a pivotal shift and opens new optimization horizons. |
| Bad | It is worth noting that the approach is not only effective but also comprehensive. |
| Good | Hypothesis: display format and device affect click-through rate. |
| Bad | In today's advertising landscape, researchers underscore the pivotal role of format. |
| Bad | The method seamlessly integrates signals, underscoring the importance of calibration. |

See [anti-ai-writing.md](anti-ai-writing.md) for the full checklist.

## Reviewer test

Read the fragment without project context. If a reader must already know SFT,
PPO, `fmt-aggregate`, or a bare CTR abbreviation, return `FAIL` with a concrete
rewrite. Also fail press-release prose or important-sounding words without facts.
