# PaperDraft

<p class="lead">A project paper draft: LaTeX and PDF under <code>paper/&lt;slug&gt;/</code>, generation from research context, agent edit proposals reviewed by a person, and Yjs/WebRTC collaboration. Git commits provide durable history.</p>

<div class="media-slot" data-media="paper-hero" data-accept="png,jpg,webp,mp4,webm"><p>Media: PaperDraft</p></div>

## How it works

**PaperDraft** opens a modal with project paper tabs, a LaTeX editor, PDF preview/build, Paper Inbox generation, collaboration status, comments, agent edit proposals, and a Git checkpoint push.

Generation places a task in `.run/paper-queue.json`. `koi-paper` uses the tree, `research.json`, reports, and an explicit figure list to write English LaTeX and build `main.tex` plus PDF. It must not invent image paths.

The browser document is a Yjs CRDT. WebRTC connects roughly five peers; signaling exchanges SDP/ICE and may relay when a data channel cannot open. Peers with different Git `HEAD` values do not synchronize text. Realtime collaboration never creates commits.

**Product rule:** agent paper-text edits remain proposals for human review. An agent or IDE assistant must never accept a proposal into the live text on the user's behalf.

## How people use the interface

1. Select a project and open **PaperDraft**.
2. Bootstrap **ResearchOS Paper Inbox** once, then mark Inbox ready.
3. Generate or regenerate the paper and wait for the tex/PDF result.
4. Edit LaTeX, save to disk, and build the PDF.
5. Review each highlighted proposal fragment and accept or reject it yourself. The editor may be read-only while a proposal is active.
6. Add comments as needed and inspect collaboration peer/signaling status. Machines must share compatible `KOI_COLLAB_*` settings.
7. Push a version when a durable Git checkpoint is needed.

## Agent workflows and commands

- `koi-paper`: claim → context → LaTeX → answer/PDF.
- Paper Inbox: `koi.paper.inbox_cli`, wake signal `PAPER_WAKE`.
- Project context already includes the tree, findings, reports, and figures.

```bash
python -m koi.paper.cli pending
python -m koi.paper.cli claim <queue_id>
python -m koi.paper.cli context <queue_id>
python -m koi.paper.cli answer <queue_id> -f paper-body.txt
python -m koi.paper.inbox_cli watch
```

## Technical details and limits

A paper normally lives in `koi-structure/paper/<slug>/` with `main.tex`, PDF, assets, and progress metadata. Queue/build code is in `koi/paper/`; client state, generation, proposals, and collaboration are in the paper modal and `web/app.js`. Collaboration uses a room derived from Git remote, slug, and file path plus signaling, STUN, and TURN settings.

Generation follows an English conference template. Cross-machine editing requires a compatible Git base, and no proposed edit reaches live text without explicit human acceptance. See `docs/paper-collaboration-spike-b.md`.

Related: [Related Work](related-work.html) · [Knowledge base](knowledge.html) · [Research Chat](chat.html) · [Architecture](index.html) · [Widgets](widgets.html)
