# Hypothesis specification (preregistration)

Complete this document BEFORE the run. It is the harness entry point: it fixes
what is being tested and the rule for accepting a conclusion so supported or
refuted is never assigned after seeing results. Copy the claim into the cause
node description in `project.md`; reviewers use the decision rule to assign the
verdict. See `docs/research-workflow.md`.

> Remove every line beginning with `>` when completing this template.

## Identifier

- hypothesis id: `c-…` (= cause node id in project.md)
- method(s): `m-…`    card(s): `…`
- author: …           date: YYYY-MM-DD

## Claim

> One falsifiable, directional sentence. Do not write “study the effect of X”;
> write “X increases Y under condition Z.”

…

## Rationale

> Why this effect is expected in 1–2 sentences; link to a KNOWLEDGE.md insight
> when available.

…

## Prediction

> Make it concrete and preferably quantitative/directional: “Newton throughput
> exceeds PhysX by at least 1.3×” or “success_rate at equal environment steps
> does not depend on num_envs beyond seed variance.”

…

## Evaluation design

- Varied factor: …
- Fixed controls: …
- Run budget: `<data volume / iterations / seeds / backend>`
- Command: `<exact launch command>`
- Metric destination: `<artifact path>`

## Primary metric and decision rule

> Name one metric and thresholds for supported, refuted, and open. The open rule
> covers insufficient evidence.

- Primary metric: … (field from the final artifact)
- supported if: …
- refuted if: …
- open if: …

## Threats to validity

> Give 2–4 factors that may distort the conclusion. Usually include seed variance
> and warm-up/asset-cache effects such as `scene_creation_s` on a cold start.

- …

## Links

- cause node: `c-…` | report: `reports/<node>/<card>.md`
- depends on insights: `rq-…` from KNOWLEDGE.md, when available

## Pre-run checklist

- [ ] Claim is falsifiable and directional
- [ ] Decision rule and supported/refuted/open thresholds fixed BEFORE the run
- [ ] Budget and controlled variables recorded
- [ ] Cause node and card exist in project.md
- [ ] Threshold accounts for seed variance
