---
name: literature-cluster-orchestrator
description: Multi-agent literature clustering for ResearchOS. Partitions selected papers across 3–4 worker agents (no overlap), each extracts an answer to the research question with supporting quotes, workers cross-judge similarity of others' findings against papers they read, then an orchestrator builds clusters + draft Related Work; a RW Critic scores how well Related Work answers the research question and a reviser fixes it from those comments before writing literature/<run_id>/report.md. Use when clustering papers on the Literature page, redesigning literature clustering, or when the user asks for multi-agent literature analysis / cluster orchestrator.
---

# Literature Cluster Orchestrator

Multi-agent clustering over a **selected paper set** and a **research question**.
Replaces single-shot Jaccard / one-LLM clustering with a three-phase protocol.

## Storage contract

```
{koi-structure}/literature/
  index.json                         # history of runs for the project (one row per run_id)
  <run_id>/                          # {query_hash}_{YYYYMMDDTHHMMSS}
    index.json                       # full machine-readable manifest
    report.md                        # primary UI render source
    similarity.json                  # worker cross-judgment table
    findings.json                    # all worker findings
    related_work.draft.md            # pre-critique Related Work
    related_work.md                  # final Related Work (after critic→revise)
    rw_critique.json                 # critic rounds + scores + comments
    workers/
      w01_findings.json
      w01_judgments.json
      ...
```

`query_hash` = first 16 hex chars of SHA-256 over whitespace-collapsed question (casefold) — fingerprint of the question only.
`run_id` = `{query_hash}_{UTC timestamp}` — unique per staging/run so the same question at different times keeps separate reports.
History upserts must key on **`run_id` only** (never replace other rows that share the same `query_hash`).

## Agent roles

| Role | Count | Input | Output |
|------|-------|-------|--------|
| **Worker** | 3–4 (or `min(4, n_papers)` if fewer papers) | Exclusive random subset of papers + question + paper text/abstract | Per-paper answer + quotes + solution summary |
| **Worker (exchange)** | same | Own papers + **other workers' findings only** (not full texts of others) | Similarity judgments vs own papers |
| **Orchestrator** | 1 | All findings + similarity table | Clusters, paper→cluster memberships, draft Related Work |
| **RW Critic** | 1 | Research question + draft Related Work (+ cluster labels for context only) | Score how well RW answers the question + actionable comments |
| **RW Reviser** | 1 (per round) | Draft RW + critic comments | Revised Related Work addressing every comment |

Workers never share the same paper. Partition is seeded by `query_hash` for reproducibility.

## Phase A — Partition

1. Take selected papers (title, url, authors, year, abstract/full text).
2. Choose `n_workers = clamp(3, 4, n_papers)` (if `n_papers < 3`, `n_workers = n_papers`).
3. Shuffle with `Random(int(query_hash[:8], 16))`, round-robin into worker buckets.

## Phase B — Per-worker extraction

Each worker receives only its papers. Prompt requirements:

- Answer the research question **using only provided text**.
- Every claim needs ≥1 **verbatim quote** from that paper.
- Emit JSON only:

```json
{
  "worker_id": "w01",
  "findings": [
    {
      "paper_title": "...",
      "paper_url": "...",
      "answer": "1-3 sentences answering the question for this paper",
      "solution_summary": "short description of the method/approach",
      "quotes": [{"text": "...", "why": "what it proves"}]
    }
  ]
}
```

Persist `workers/wXX_findings.json`. Merge into `findings.json`.

## Phase C — Cross-exchange judgments

For each worker W:

1. Build a packet of findings from all workers except W (titles, answers, solution summaries, quotes — **no** full paper bodies of others).
2. Ask W: for each foreign finding, is the solution **similar** to any paper W read?
3. Emit JSON only:

```json
{
  "worker_id": "w01",
  "judgments": [
    {
      "their_paper_title": "...",
      "my_paper_title": "... or null",
      "similar": true,
      "confidence": 0.0,
      "rationale": "..."
    }
  ]
}
```

Build `similarity.json`:

```json
{
  "edges": [
    {
      "a": "Paper A",
      "b": "Paper B",
      "similar_votes": 2,
      "dissimilar_votes": 0,
      "mean_confidence": 0.8,
      "rationales": ["..."]
    }
  ]
}
```

Undirected edge aggregation: count votes where `similar=true` from either direction; keep rationales.

## Phase D — Orchestrator clustering

Input: question, findings, similarity edges (prefer edges with `similar_votes >= 1` and `mean_confidence >= 0.5`).

Orchestrator must:

1. Propose **clusters** for groups of papers linked by similarity (connected components as a hint; LLM may refine).
2. Name each cluster and write a **similarity basis** (what is shared in the *solution*, not just topic).
3. For **every paper**, list membership options (`cluster_keys` + `primary_cluster_key` + score).
4. Write a **Related Work** section answering the original question using cluster structure — follow **Related Work prose style** below (mandatory).

Emit JSON:

```json
{
  "clusters": [
    {
      "key": "slug",
      "label": "Short name",
      "description": "What solutions share",
      "similarity_basis": "Concrete shared mechanism",
      "paper_titles": ["..."]
    }
  ],
  "paper_assignments": [
    {
      "paper_title": "...",
      "primary_cluster_key": "slug",
      "cluster_keys": ["slug"],
      "membership_scores": {"slug": 0.9},
      "rationale": "..."
    }
  ],
  "related_work_markdown": "..."
}
```

## Related Work prose style (mandatory)

`related_work_markdown` / `related_work.md` must read like a short survey paragraph (or a few continuous paragraphs), **not** like a cluster dump.

### Hard bans

- **Never** one subsection / one paragraph per cluster (`## Cluster A`, then `## Cluster B`, …).
- **Never** bullet lists of papers or “Cluster 1: … / Cluster 2: …” outlines.
- **Never** paste cluster `label` / `description` / `similarity_basis` as standalone blocks.

Clusters are an *internal* scaffold for who goes with whom. In Related Work they stay invisible as headings — only the *ideas* and *contrasts* remain.

### Required shape

1. Number papers once (stable order: primary cluster order, then title) as `[1]`, `[2]`, … — either inline on first mention or a short reference list at the end of `related_work.md` (title + url). In the prose body, cite by number only.
2. **Generalize hard** inside each affinity group: one clause for what `[1, 2, 3]` share as a *solution*, not a tour of each paper.
3. **Thread clusters with contrast**, not isolation. Typical cadence:

   > Papers [1, 2, 3] propose … (the group's shared solution). In contrast, papers [4, 5] use … . A separate line of work appears in [6, 7], where …

4. Answer the research question with this narrative: shared mechanisms → how other groups differ → residual outliers in one closing sentence if needed.
5. Prefer dense survey prose over paper-by-paper paraphrase. Name a method only when it is the shared basis of the group.

### Good vs bad

Bad (cluster paragraphs):

```text
## Neural CTR
Papers A, B use deep models...

## Feature interaction
Papers C, D model crosses...
```

Good (prose + contrast):

```text
Papers [1, 2, 3] estimate CTR with deep models over raw user and advertisement features.
In contrast, [4, 5] explicitly model pairwise feature interactions and rely little on sequence representations.
A separate approach appears in [6], where clicks are predicted from an interaction graph rather than a tabular feature vector.
```

Language: write Related Work in English. Keep the tone concrete and avoid empty survey filler such as “important contribution” or “opens new horizons.”

## Phase E — RW Critic → revise

After the orchestrator draft, a **separate** RW Critic agent reviews Related Work **only** against the research question (not against cluster aesthetics alone).

### Critic input

- Original research question (verbatim)
- Draft `related_work_markdown`
- Optional: cluster labels + one-line similarity bases (context; critic must not demand per-cluster paragraphs)

### Critic output (JSON only) → `rw_critique.json`

```json
{
  "answers_question": false,
  "score": 0,
  "summary": "1-2 sentences: what the RW currently answers vs what the question asked",
  "gaps": [
    "Concrete missing angle relative to the question"
  ],
  "comments": [
    {
      "severity": "quoted or paraphrased span that is weak / off-question",
      "issue": "why it fails to answer the question",
      "fix": "what to change"
    }
  ],
  "pass": false
}
```

Scoring (0–100):

| Band | Meaning |
|------|---------|
| 80–100 | Directly answers the question; contrasts map to the asked distinction |
| 50–79 | Partially on-topic; major facets of the question under-addressed |
| 0–49 | Survey of papers that drifts from the question |

`pass = true` only if `score >= 80` **and** `answers_question = true` **and** no blocking `gaps`.

Critic focus (in order):

1. Does the prose **answer the stated question**, or only summarize papers?
2. Are the contrasts the ones the question implies (methods / settings / claims), not random groupings?
3. Is anything in the question left unanswered that the selected papers could support?
4. Style check: still continuous prose with `[n]` cites (flag if cluster-split crept back in).

### Revision loop

1. Save draft as `related_work.draft.md`.
2. Run critic → append round to `rw_critique.json` (`rounds: [...]`).
3. If not `pass`: RW Reviser rewrites full Related Work addressing **every** comment and gap; keep prose style rules; do not invent papers.
4. Reviser output JSON: `{ "related_work_markdown": "...", "addressed": ["comment → how fixed"] }`.
5. Repeat critic → revise **at most 2 rounds**. After round 2, keep the latest draft even if not `pass`, but leave the final critique on disk.
6. Final text → `related_work.md` (and embed in `report.md`).

Halt: if after a revision any critic comment is ignored without reason in `addressed`, rewrite again in the same round before re-critiquing.

## Phase F — Write `report.md`

Orchestrator host / agent writes `report.md` with:

1. Title = question
2. Meta: hash, date, worker count, paper count, RW critic score
3. `## Clusters` — **for each cluster**, in this exact shape:

```markdown
### <Cluster name>

<Cluster description>

#### <Paper title>
year · authors · url

**TLDR.** <1 short sentence — solution_summary>

**Answer to the question.** <how this paper answers the research question>

**Quotes.**

> verbatim quote from the paper
>
> — why this quote answers the question
```

Every paper in the cluster must have TLDR + answer + ≥1 quote from worker findings (`findings.json`). Do not list bare titles without these fields.

4. `## Paper assignments` — table or bullets
5. `## Related Work` — **final** revised prose (not the pre-critique draft)
6. `## Similarity evidence` — compact summary of high-confidence edges
7. Optional `## RW critique` — final score + summary (short)

UI cluster detail panel uses the same per-paper fields from `index.json` (`tldr`, `query_answer`, `quotes`).

Also put a top-level `papers` array in `index.json` where each paper has `cluster_key` (alias of `primary_cluster_key`) plus the same `tldr` / `query_answer` / `quotes`. Prefer nesting the same objects under `clusters[].papers` — the UI reads either shape.

UI renders this markdown (plus structured `index.json` for cluster tiles).

## Fallback (no LLM backend)

- Phase B: abstract-heuristic answers (first sentences + title tokens as pseudo-quotes).
- Phase C: token-Jaccard on `solution_summary` ≥ 0.22 ⇒ similar.
- Phase D: connected components → cluster labels from top shared tokens; Related Work = one continuous prose paragraph contrasting groups (`[1,2,3]` vs `[4,5]`), never per-cluster headings.
- Phase E: lightweight heuristic critic — token overlap of question vs RW; if low, prepend one sentence that restates the question and how the groups answer it; write `rw_critique.json` with `backend: heuristic_fallback`.

Mark `cluster_backend` as `multi_agent` or `heuristic_fallback` in `index.json`.

## Chat bootstrap (preferred — no LLM API keys)

Default Literature-page flow:

1. User selects papers + enters a research question.
2. UI calls `POST /projects/{id}/literature/cluster/stage` — writes `literature/<run_id>/input.json` + `PROMPT.md` (no agent backend).
3. User pastes the returned prompt into a Cursor / agent chat.
4. Agent loads this skill, reads `input.json`, runs Phases A–F (including RW critic → revise), writes `report.md` + manifest.
5. Literature page polls `GET .../literature/{run_id}` until `report.md` appears.

When the user pastes a staged prompt (or says “run literature cluster on staged input”), follow the skill and the paths in the prompt — do not ask for API keys.

## ResearchOS wiring

- Stage (no API agent): `POST /projects/{id}/literature/cluster/stage`
- Optional server-side LLM run: `POST /projects/{id}/literature/cluster`
- History / load: `GET .../literature`, `GET .../literature/{run_id}`
- Literature page: left = paper collection; center = question → **copy prompt**; right = **query history** opening past `report.md` runs.
- Do not write new runs under `paper_answers/` for this flow.

## Halt / quality rules

- Every selected paper appears in exactly one **primary** cluster (soft multi-membership allowed via `cluster_keys`).
- Quotes must be substrings of provided paper text when full text exists; otherwise allow abstract excerpts.
- Orchestrator must not invent paper titles not present in findings.
- Related Work must be continuous contrasting prose with `[n]` cites — fail and rewrite if it is split into per-cluster headings or paragraphs.
- Final Related Work must go through RW Critic; if `pass=false`, revise using the comments before writing `report.md`.
- Each cluster block in `report.md` must include per-paper **TLDR**, **answer to the question**, and **verbatim quotes** (from worker findings) — bare paper title lists are a halt condition.
