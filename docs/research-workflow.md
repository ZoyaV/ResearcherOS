# Knowledge accumulation process

How knowledge moves from a question to a registry entry. Project files are the
source of truth; derived `KNOWLEDGE.md` files are rebuilt automatically.

Steps 3–4 and 7–8 are automated. Running
`python -m koi.projects.report_ingest.cli <project> <card>` delegates the check
to an agent (Claude Code / Cursor), which writes `.run.md` from the template.
`koi/projects/report_ingest/` then ingests the report (verdict from §5.1,
insights from the §5.2 JSON block, card → done) and automatically rebuilds the
knowledge base. Manual review using the matrix below remains the recommended
quality check; ingest a reviewed report with
`python -m koi.projects.report_ingest.cli <project> <card> --ingest-only`.
See `docs/human/knowledge-base.md` for details and environment variables.

## Steps

1. Pre-register. Complete `agents/skills/koi-execute-card/hypothesis-spec.md`.
   The claim becomes the cause-node description; keep the decision rule at hand
   because it determines the verdict.
2. Create a node and card. In `project.md`: cause (hypothesis) → cause_evidence
   (how it is evidenced) → method (how it is tested), plus a kanban card in backlog.
3. Run. Move the card from backlog → running. Save metrics in a reproducible
   artifact referenced by the report.
4. Write the working run report. The executing agent fills
   `agents/skills/koi-report-review/experiment-report.md` →
   `reports/<node>/<card>.run.md`: what ran, results, evaluation of the decision
   rule, and a “Knowledge base submission” block with proposed verdict, insights
   in research.json format, and a recommendation about form. This is the review
   input and contains paths and raw numbers. For automatic integration, §5.2 must
   contain exactly one fenced ```json block with an array of no more than three
   insights (research.json fields), and §5.1 must contain
   `` `<node-id>` → … **verdict** ``.
5. Review the submission. Use the matrix below to decide HOW to integrate it:
   accept as written, downgrade to tentative+open, split, reject, or retain a
   methodological insight.
6. Create the public report. Convert `.run.md` to `reports/<node>/<card>.md` using
   `agents/skills/koi-report-review/report-skeleton.md` (remove HOW-TODO, use
   public names, follow `report-rules.md`) and add `card_id → path` to
   `reports/index.json`.
7. Record insights and verdict. Put accepted insights in `research.json` (no more
   than three per method: question/answer/narrative/certainty/importance/card_id)
   and set `verdict:` on the cause node.
8. Integrate automatically. The `save_project` hook rebuilds the project knowledge
   base: it updates `knowledge/hypotheses.md` and the `KNOWLEDGE.md` table of
   contents, and appends the exact changes to `KNOWLEDGE_LOG.md` (verdict changes,
   new or updated insights, and new documents).

## Project knowledge documents (`projects/<id>/knowledge/`)

Lessons not tied to one hypothesis (setup, launch, scripts, pitfalls, open
questions) are separate `.md` files in the project's `knowledge/` directory.
Convention: the first line is `# Title`; the first paragraph after it is a
one-to-two-sentence summary used in the `KNOWLEDGE.md` table of contents. Name
files `NN-name.md`, where NN defines their order. A new file is discovered on the
next project save and recorded in the log. Recommended set: `00-overview`,
`10-setup`, `20-running`, `30-scripts`,
`40-gotchas`, `50-open-questions`.

## Decision matrix: how to integrate

The reviewer takes the “Knowledge base submission” block from `.run.md` and
chooses its form. The agent's submission is a proposal, not a final judgment;
alignment with the decision rule and threats in report §4 determines the form.

| Situation (from §§3–4 of the working report) | Integration form |
|---------------------------------------|------------------|
| The rule threshold is passed with margin and the finding is robust to variation | Accept as written: `certainty=definite`, verdict `supported`/`refuted` |
| The result is borderline or the effect is comparable to seed variance | Downgrade: `certainty=tentative`, verdict `open`, caveat in narrative, and run again |
| The run produced several distinct findings | Split into no more than three insights per method, each with its own question and card_id |
| Methodological error (cold cache distortion, failed run, wrong metric) | Reject: write no insight, record the reason in `.run.md`, and rerun |
| The prediction was refuted, but the run taught something about the metric itself (for example, success_rate hit a ceiling) | Methodological insight: `refuted` verdict for the prediction plus an insight about the right measurement |

Implement the selected form through steps 6–8: public report → research.json +
verdict → registry rebuild.

## Review checklist (definition of done for an insight)

- [ ] The specification's decision rule is applied explicitly; the verdict follows from numbers, not an impression.
- [ ] The report follows the skeleton: §1 why (measurable goal), §2 primary metric, §3 setup, §4 results.
- [ ] The research.json insight is honest: no more than three per method, `definite` only when the threshold is passed with margin, and card_id points to the source card.
- [ ] Variance is considered: the finding is robust across seeds (see H3), otherwise `certainty=tentative`.
- [ ] Cold start/cache does not distort the comparison (`scene_creation_s` on the backend's first run is separated from training throughput).
- [ ] The report uses public names and has no local paths in §§1–2, per `koi-report-review`.

## Verdict

- supported — the decision rule is satisfied and the finding is robust.
- refuted — the prediction failed under the same rule.
- open — evidence is insufficient, for example because the effect lies within seed variance; another run is needed.

Change a verdict only after re-evaluating the data. Rebuild KNOWLEDGE.md after a
verdict or insight changes.
