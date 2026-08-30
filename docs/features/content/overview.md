# How ResearcherOS is structured

<p class="lead">ResearcherOS connects hypotheses, experiments, reports, accumulated knowledge, and paper text as one Research Project state. The local app and agents edit the same files; Hub publishes read-only snapshots. Experiment code remains separate. Git provides durable history, report processing turns runs into findings, and a separate channel supports simultaneous paper editing.</p>

<div class="media-slot" data-media="overview-hero" data-accept="png,jpg,webp,mp4,webm"><strong>ResearcherOS overview</strong><p>Diagram or demonstration of Research Project, local application, and Hub.</p></div>

## Architecture in three layers

<div class="layer-grid">
  <article class="layer-card layer-card--project"><span class="layer-card__kicker">1 · Research Project</span><h3>Research state</h3><p>Hypothesis tree, experiment kanban, reports, knowledge, paper, agent workflows, and widgets live in project files. Experiment code is separate.</p></article>
  <article class="layer-card layer-card--local"><span class="layer-card__kicker">2 · Local</span><h3>Local ResearcherOS</h3><p>The web client and local API read and edit Research Project files through the tree, kanban, monitor, knowledge base, Related Work, Research Chat, PaperDraft, and widgets.</p></article>
  <article class="layer-card layer-card--hub"><span class="layer-card__kicker">3 · Hub</span><h3>ResearcherOS Hub</h3><p>Hub publishes read-only snapshots. It displays research state but never replaces the local project as the source of truth.</p></article>
</div>

## Complete diagram

<div class="schema-frame schema-frame--embed"><iframe src="full_schema.html?embed=1&v=4" title="ResearcherOS architecture diagram" loading="lazy"></iframe></div>

<p class="callout"><strong>How to read it.</strong> Researchers work in separate local copies. Git exchanges durable state, Hub shows a read-only published snapshot, and collaborative editing transfers changes to the open paper without creating commits.</p>

## Research Project: source of research state

A Research Project is a set of files, not a server or database:

`problem → causes → hypotheses → methods → experiments → reports → verdicts and findings`

The recommended location is `tree/<repo>/koi-structure/`, discovered through `project.md`.

<div class="tree-list">tree/&lt;repo&gt;/koi-structure/<br>├── project.md <span class="muted">← hypothesis tree and method kanban</span><br>├── research.json <span class="muted">← method questions and findings</span><br>├── knowledge/ <span class="muted">← curated notes</span><br>├── reports/ <span class="muted">← experiment reports</span><br>├── paper/ <span class="muted">← paper assets and LaTeX</span><br>├── skills/ <span class="muted">← project agent workflows</span><br>└── widgets/ <span class="muted">← project widgets</span></div>

`project.md` links hypotheses to methods and gives each method a kanban. Reports and findings enrich the model, but a raw run log is not research knowledge by itself. Composite views may combine several projects while leaving source data in its repositories.

### Local and Git-synchronized projects

Git is optional. Set `git_repo: true` for synchronization and place research materials in a `koi/research` worktree while code remains beside it.

```bash
python -m koi.projects.install_cli install <name>
python -m koi.projects.install_cli install <name> --create
python -m koi.projects.sync_cli push --project-id <project-id>
python -m koi.projects.sync_cli pull --project-id <project-id>
```

Push copies current materials, commits, and sends the branch. Pull refuses to overwrite a dirty research worktree. Runtime state under the engine's `.run/` is not part of the Research Project.

## Local ResearcherOS and Hub

The local FastAPI server and web client expose all editable project views. Agents use the same files and workflows; `ProjectMount` resolves recommended and supported legacy layouts. Hub registers a repository branch (normally `koi/research`) and publishes public, network, or unlisted read-only snapshots. Public project skills enter the shared catalog only when both project and skill are public. A shared widget catalog remains future work.

## Three state-coordination mechanisms

1. **Git** provides reproducible file history and exchange between local copies.
2. **Result processing** turns a run into structured research state. `report_ingest` reads a valid §5 verdict and insights; alternatively, a new done card enters the completed-research queue when it has no finding. `save_project` rebuilds generated knowledge indexes but never invents one curated note per report.
3. **Paper collaboration** uses Yjs CRDT plus WebRTC or server relay for a small group. Peers need compatible Git state and CRDT epoch; realtime changes do not create commits. Relay-only mode does not guarantee strict room isolation by `HEAD`, so compatible Git state remains necessary.

External editor changes become pending proposals. A person accepts, rejects, or resolves fragments before any proposal reaches the live paper.

The boundaries are deliberate: a realtime paper change is not a durable Git version, and a completed computation is not a research finding until ingestion or an agent records it.

## Local feature catalog

<div class="feature-list">
<a class="feature-row" href="research-tree.html"><span class="feature-row__num">01</span><span><p class="feature-row__title">Research tree</p><p class="feature-row__desc">Nodes, verdicts, project.md structure, and method kanban links.</p></span><span class="feature-row__meta">open</span></a>
<a class="feature-row" href="kanban.html"><span class="feature-row__num">02</span><span><p class="feature-row__title">Experiment kanban</p><p class="feature-row__desc">Card states, dependencies, and reports.</p></span><span class="feature-row__meta">open</span></a>
<a class="feature-row" href="monitor.html"><span class="feature-row__num">03</span><span><p class="feature-row__title">Run monitor</p><p class="feature-row__desc">Live status, logs, metrics, and charts.</p></span><span class="feature-row__meta">open</span></a>
<a class="feature-row" href="knowledge.html"><span class="feature-row__num">04</span><span><p class="feature-row__title">Knowledge base</p><p class="feature-row__desc">Structured findings, generated summaries, and curated notes.</p></span><span class="feature-row__meta">open</span></a>
<a class="feature-row" href="chat.html"><span class="feature-row__num">05</span><span><p class="feature-row__title">Research Chat</p><p class="feature-row__desc">Questions and answers grounded in project context.</p></span><span class="feature-row__meta">open</span></a>
<a class="feature-row" href="related-work.html"><span class="feature-row__num">06</span><span><p class="feature-row__title">Related Work</p><p class="feature-row__desc">Library, arXiv, Zotero, clusters, and review drafts.</p></span><span class="feature-row__meta">open</span></a>
<a class="feature-row" href="paper.html"><span class="feature-row__num">07</span><span><p class="feature-row__title">PaperDraft</p><p class="feature-row__desc">LaTeX, reviewed proposals, Yjs collaboration, and Git history.</p></span><span class="feature-row__meta">open</span></a>
<a class="feature-row" href="widgets.html"><span class="feature-row__num">08</span><span><p class="feature-row__title">Widgets</p><p class="feature-row__desc">Project panels using the local API.</p></span><span class="feature-row__meta">open</span></a>
</div>
