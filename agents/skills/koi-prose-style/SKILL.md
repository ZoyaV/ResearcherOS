---
name: koi-prose-style
description: >-
  Review and rewrite KOI user-facing prose (kanban cards, project.md nodes,
  research question/narrative, knowledge docs) for natural-language style and
  against Wikipedia Signs of AI writing tells. Launches a readonly style-reviewer
  subagent before saving. Use when adding or editing cards on a board,
  descriptions, hypotheses, method titles, or any text shown in the KOI UI
  without extra documentation.
---

# KOI: user-facing prose style

Before writing any **human-readable** project text — node titles and
descriptions, kanban card `title`/`desc`, `question`/`narrative` in
`research.json`, or curated `knowledge/*.md` — run the cycle **draft → read-only
subagent review → rewrite → review again**. Write only after `PASS`.

This skill does not cover technical fields such as `id`, `answer`, paths, or
fenced report JSON; AGENTS.md format gates apply there.

## When to run

1. Adding or changing kanban cards.
2. Editing `koi-structure/project.md` problem, cause, method, or remediation.
   Before changing node titles, reread `koi-structure/onboard-brief.md` when it
   exists and preserve its high-level goals.
3. Writing `question` / `narrative`, including inside `koi-done-research`.
4. Writing curated `projects/<id>/knowledge/*.md` documents.
5. Any text a person sees in the UI without opening a report or glossary.
6. During **koi-project-onboard**, apply these rules to every user-facing message
   and require a subagent `PASS` when fixing a framing layer and before writing
   `koi-structure/project.md`.

For a conclusion from a done card, use `koi-done-research` first but still run
this workflow on `question` and `narrative`.

## Mandatory style rules

### A. Plain English

Use natural English and avoid mixing languages within one phrase. Explain an
unfamiliar metric or method before giving its abbreviation: for example,
“click-through rate (CTR).” Every project label must make sense without separate
project documentation.

### B. Avoid formulaic AI prose

Use Wikipedia’s “Signs of AI writing” checklist
and the short UI checklist in [anti-ai-writing.md](anti-ai-writing.md). Check for:

1. Empty prestige words such as groundbreaking, nuanced, seamless, tapestry,
   delve, underscore, foster, pivotal, and opens new horizons.
2. Throat-clearing such as “It is important to understand,” “In the context of,”
   “It is worth noting,” and empty overall/in-summary endings.
3. Rhetorical filler: “not only X but also Y,” forced triples, and false ranges.
4. Significance claims without evidence, including “marks a shift,” “testament,”
   and trailing “highlighting/underscoring” clauses without a measurable result.
5. Vague unnamed experts or researchers.
6. Em-dash piles, decorative bold/emoji, unnecessary Title Case, and visible placeholders.
7. Ornate verbs such as “serves as” or “boasts” where “is” or “has” works.

These signs are probabilistic; a cluster in one fragment is `FAIL`. Repair with
specific meaning, not another AI-sounding synonym.

### Map-title length (hard limit)

A **tree node title** (the first line after `# problem:`, `## cause:`,
`### remediation:`, `### cause_evidence:`, or `#### method:`) and a **kanban
card title** (visible text before `<!-- id:… -->`) should contain at most
**8 words** by default.

**Only during a koi-project-onboard clarity loop:** if a cold reader twice fails
to understand a critical node at eight words, that title may use up to 12 words.
All others remain at most eight. More than eight without that recorded exception
is `FAIL`.

Put metrics, conditions, baselines, and script paths in the node description or
card `desc`, not the title.

| | Example |
|---|---------|
| Good node title (6 words) | Policy fails in unseen environments |
| Good description | After reinforcement learning in one environment, the successful-episode rate falls outside the training distribution. |
| Bad title | The language-model agent after reinforcement learning in one environment performs worse outside the training distribution |

For an overlong title, suggest a short title plus a description.

### Additional rules

| Area | Writer | Reviewer |
|------|--------|----------|
| UI language | English; one language per phrase | Mixed languages without explanation fail |
| Abbreviations | Explain meaning before `(CTR)`, `(CPC)`, `(SFT)`, etc. | Bare jargon such as `CTR analysis` fails |
| Node/card title | At most 8 words; at most 12 only for a critical onboard clarity exception | Protocol details in title or over limit fail |
| Description / `desc` | Details, metrics, conditions, baselines | Empty description paired with an overloaded title fails |
| Kanban card | Short title; output and details in `desc` | Jargon or an internal id instead of meaning fails |
| `research.json` | `question` and `narrative` are reader-facing; raw metrics go in `answer` | Training steps and raw numbers in narrative fail |
| Identifiers | `id:fmt-aggregate` in an HTML comment is fine | Visible `fmt-aggregate` / `kb-sft` fails |
| Anti-AI | Concrete fact and plain verb | Clusters of AI tells or empty significance fail |

Canonical examples: [examples.md](examples.md),
[anti-ai-writing.md](anti-ai-writing.md), and
`bicycle_problem/koi-structure/project.md`.

## Workflow

### 1. Draft

Collect **only the fragments being reviewed**, one block per card or field.
Do not send a whole-file diff.

```text
## Fragment: <card id:… | cause node:… | research question rq-…>
<card title or node title>
desc: <when present>
---
<remaining visible text>
```

### 2. Read-only subagent reviewer

Launch exactly one subagent:

- `subagent_type`: `generalPurpose`
- `readonly`: `true`
- `run_in_background`: `false`
- `description`: `KOI prose style review`

Prompt:

```text
You are a KOI prose style reviewer. Read-only. Do not edit files.

Mandatory rules:
1) Use natural English for a cold reader; do not mix languages. Explain an
   unfamiliar metric in plain language before its abbreviation, such as
   click-through rate (CTR).
2) Flag clusters of Wikipedia Signs of AI writing tells:
   - empty prestige words (groundbreaking, nuanced, seamless, tapestry, delve,
     underscore, foster, pivotal, crucial)
   - throat-clearing and empty wrap-ups (It is worth noting; It is important to
     understand; overall/in summary with no new fact)
   - rhetorical filler (not only X but also Y; forced triples; false ranges)
   - significance puffery without a measurable consequence; trailing
     “highlighting/underscoring” clauses
   - vague unnamed experts/researchers
   - em-dash piles, unnecessary Title Case, decorative emoji/bold, visible placeholders
   - ornate verbs instead of is/has (serves as, boasts)
   Repair with specific claims, not synonym swaps.
3) Node and kanban titles: at most 8 words; details belong in body/desc.
4) No bare jargon without a plain-English explanation.
5) question/narrative contain no raw metrics; those belong in answer.
6) Visible text contains no internal ids such as fmt-aggregate or kb-sft.

Fragments:
<paste fragments from step 1>

Reference anti-ai-writing.md and examples.md when needed.

Output format:
Line 1: exactly PASS or FAIL
If FAIL: markdown table Fragment | Problem | Suggested rewrite
If PASS: one short sentence explaining why.
```

### 3. Rewrite loop

- `PASS` → continue to step 4.
- `FAIL` → rewrite only named fragments using Suggested rewrite, then rerun step 2.
- Allow at most three review iterations. After the third FAIL, show the table to
  the user and ask whether to save as-is or revise manually. Do not write
  without explicit approval.

### 4. Save

Only after PASS, write or replace the target file. Tell the user briefly that
koi-prose-style passed and state the iteration count or key rewrites.

## Quick self-check when no subagent is available

Read every fragment aloud. If it is unclear without project knowledge, rewrite
it. Explain abbreviations, then scan [anti-ai-writing.md](anti-ai-writing.md)
for prestige words, throat-clearing, rhetoric, and puffery. This is a fallback;
prefer the full subagent cycle when available.

## Related skills

- `koi-project-onboard` — repository attachment; prose gate on frames and final skeleton
- `koi-report-review` — four critics for report Sections 1–N
- `koi-done-research` — done-card conclusion; review narrative/question here
- `koi-knowledge-curator` — curated documents; review before saving
- `koi-project-sync` — commit after `koi-structure/` changes
- Paper writing checklist: `.cursor/skills/paper-orchestra-shared/writing_quality_check.md`
