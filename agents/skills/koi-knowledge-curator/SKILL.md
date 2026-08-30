---
name: koi-knowledge-curator
description: >-
  Deep cross-experiment synthesis of the KOI knowledge base: review accumulated
  insights and run reports, then write curated knowledge documents (patterns,
  contradictions, applicability limits, open questions). Use when the user asks
  to summarize knowledge, when several cards reached done since the last
  curation, or when KNOWLEDGE_LOG.md grew noticeably.
---

# KOI: curate the knowledge base

The generated layer (`KNOWLEDGE.md`, `knowledge/hypotheses.md`, and
`KNOWLEDGE_LOG.md`) is built deterministically from reports and research.json.
It is accurate but flat: a list of verdicts and insights without relationships.
An agent writes the deeper curated layer under
`projects/<id>/knowledge/<topic>.md`. Never edit generated files; they are
overwritten. Curated files are added to the index automatically.

## When to run

1. The user asks to summarize knowledge or is preparing a paper, report, or talk.
2. At least three new done cards accumulated since the last curation, visible in
   `projects/<id>/KNOWLEDGE_LOG.md`.
3. After a series of ingests within one method or hypothesis.

## Workflow

### 1. Gather evidence

- `projects/<id>/KNOWLEDGE_LOG.md` — what was added and when
- `projects/<id>/research.json` — all insights (question, answer, narrative,
  certainty, importance, card_id)
- source reports under `projects/<id>/reports/<node>/<card>.run.md` for affected
  cards — measurements, decision rules, and Section 4 threats/caveats

### 2. Cross-analyze what deterministic rules cannot

- **Connections:** which insights from different experiments combine into one conclusion?
- **Contradictions:** where do results diverge as seed, scale, or range changes?
  Do not smooth them over; record both sources.
- **Applicability limits:** under what report caveats does a conclusion stop holding?
- **Open questions:** what should be tested next? These can become kanban cards.

### 3. Write a curated document

Create `projects/<id>/knowledge/<topic>.md`:

- `# Title`; the first paragraph is the index summary
- every claim links to a source `.run.md` report and gives measured values
- mark `certainty: tentative` insights as preliminary
- end with an Open questions section

### 4. Rebuild indexes

The project rebuilds on the next `save_project` from the UI or ingest. The
`koi/knowledge` package updates the project index whenever the project is saved.

## Quality rules

- No claim without a source-report link and numbers.
- A contradiction is more valuable than a smooth story: write explicitly that
  experiment A found X while B found Y under different conditions and that the
  boundary remains unknown.
- Do not duplicate generated lists. A curated document explains relationships
  and meaning rather than repeating insights.
