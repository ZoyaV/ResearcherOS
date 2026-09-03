# Research tree

<p class="lead">A research specification on a mind map, from an observed problem to causes, tests, interventions, and methods. Nodes live in <code>project.md</code>; local ResearcherOS renders and edits the same file.</p>

<div class="media-slot" data-media="research-tree-hero" data-accept="png,jpg,webp,mp4,webm"><p>Media: research tree</p></div>

## How it works

The tree answers: what is wrong → why we think so → how to test or remedy it → which protocol to use.

| Parent | Allowed children |
|---|---|
| root | problem |
| problem | cause |
| cause | cause evidence, remediation hypothesis |
| evidence or remediation | method |
| method | none; runs live only on its kanban |

File types are `problem`, `cause`, `cause_evidence`, `remediation`, and `method`. The short map label “Hypothesis” means a remediation hypothesis, not a cause verdict. Legacy `experiment` leaves are parsed but hidden and cannot be added.

A cause has `open`, `supported`, or `refuted` status. Only causes display ✔/✗ verdict badges. A method owns a kanban; clicking it opens the board and a progress bar appears beneath the map node. Claims must remain falsifiable: one successful run is provisional support, not permanent proof.

## How people use the interface

Select a project, open and edit nodes, then save changes back to `project.md`. Report ingestion may update a cause verdict only when the report explicitly declares it.

| Action | Non-method | Method |
|---|---|---|
| Click | node modal | kanban |
| Double-click | node modal | focus camera, not kanban |
| Context menu | node modal | kanban |

Evidence and remediation nodes can add a method; map + buttons appear wherever children are allowed. The root problem cannot be deleted. Other deletions require typing the first words of the title exactly. Canvas controls zoom, show the whole laboratory or current project, and pan. Hub is read-only. The ordinary node modal does not set cause verdicts.

## Agent workflows

- `koi-project-onboard` creates problem → cause → evidence/remediation → method, writes `project.md` and `onboard-brief.md`, then installs the project.
- `koi-prose-style` keeps titles short, natural, and free of AI clichés; onboarding requires PASS before writing.
- `koi-grill-experiment` specifies a card under one selected method rather than rebuilding the tree.
- `koi-done-research` writes a completed card's question, answer, and narrative to `research.json`; it does not set cause verdicts.
- `koi-knowledge-curator` curates `knowledge/` without rewriting the tree.

`report_ingest` is a separate path that can update a cause verdict from an explicit report declaration.

## Technical details

Canonical storage is `tree/<repo>/koi-structure/project.md` on a `koi/research` worktree. Markdown heading depth defines node depth; each heading contains `type: id`.

```markdown
# problem: n-problem

Problem title and description

## cause: n-cause-memory

verdict: open

### remediation: n-rem-episodic

#### method: m-ab-memory

<!-- koi:kanban board-… -->
| backlog | running | done |
| --- | --- | --- |
```

Parsing and serialization live in `koi/core/md_io.py`; domain rules in `koi/core/models.py`; project loading in `koi/adapters/repository.py`. Node POST/PATCH/DELETE APIs accept title, description, and research questions, but PATCH does not accept verdict. Verdict changes require `project.md` editing or valid report ingestion.

The client map is implemented in `web/index.html`, `web/app.js`, and `web/lab-canvas.js`; SVG edges and layout are calculated client-side. Findings link by `method_id` and `card_id`, and Hub exposes the same tree as a read-only snapshot.

## Limits

Cause verdicts are not edited in the regular modal. Double-clicking a method focuses it rather than opening kanban. Legacy experiment leaves remain hidden. Hub cannot add or remove nodes, and the root problem cannot be deleted.

Related: [Experiment kanban](kanban.html) · [Run monitor](monitor.html) · [Architecture](index.html) · [Knowledge base](knowledge.html)
