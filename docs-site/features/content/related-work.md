# Related Work

<p class="lead">A literature workspace for search, Zotero, or CSV collections; a research question; clustered analysis; and a Related Work draft. Results live in <code>koi-structure/literature/</code>, and Literature Inbox wakes the agent.</p>

<div class="media-slot" data-media="related-work-hero" data-accept="png,jpg,webp,mp4,webm"><p>Media: Related Work</p></div>

## How it works

Open **RelatedWork** from the workspace. Collections can come from keyword/arXiv search, a Zotero user and collection, or a local CSV.

1. Collect and select papers.
2. Enter a research question.
3. Start prompt analysis or clustering; agents read selected texts relative to the question.
4. Review clusters, findings, and the Related Work draft.
5. Access run history through `literature/index.json` and **Past questions**.

The multi-agent clustering workflow assigns non-overlapping papers to 3–4 workers, exchanges similarity judgments, builds clusters and a draft, then runs critic and editor passes. Each run stores `report.md` and `related_work.md`.

The shorter UI queue writes `.run/related-work-queue.json`; `koi-related-work` claims the task, writes 2–5 paragraphs using only prompt/cluster facts, and returns Markdown to the page. Article morphology is a separate single-paper claim-graph tool and does not replace collection analysis.

## How people use the interface

1. Open RelatedWork and select a project if needed.
2. For an empty collection, choose Search, Zotero, or CSV; then select all/reset or add more.
3. Enter a question and start analysis. Bootstrap **ResearchOS Literature Inbox** once and mark it ready.
4. Watch agent status and the timer, then inspect reports, findings, and clusters.
5. Search settings choose internet/library mode and store Zotero credentials.

## Agent workflows

- `literature-cluster-orchestrator`: workers → similarity table → clusters → Related Work → critic → run files.
- `koi-related-work`: short UI-queue synthesis returned to the page.
- Literature Inbox: `koi.related_work.inbox_cli`, wake signal `RELATED_WORK_WAKE`.
- Article morphology: external workflow and `morphology.html` for one paper.

```bash
python -m koi.related_work.cli pending
python -m koi.related_work.cli claim <queue_id>
python -m koi.related_work.cli context <queue_id>
python -m koi.related_work.cli answer <queue_id> -f related-work.md
python -m koi.related_work.inbox_cli watch
```

## Technical details and limits

```text
koi-structure/literature/
  index.json
  <run_id>/
    index.json
    report.md
    findings.json
    similarity.json
    related_work.draft.md
    related_work.md
    rw_critique.json
    workers/…
```

The client is `web/literature.html` plus `web/literature.js`; queue code is `koi/related_work/`. Settings use `koi-rw-settings` in localStorage. Clustering requires selected papers and a question. Queue synthesis must not invent papers, and PDF/full-text availability depends on downloaded or attached library material.

Related: [Research Chat](chat.html) · [Knowledge base](knowledge.html) · [Architecture](index.html) · [PaperDraft](paper.html)
