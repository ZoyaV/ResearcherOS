# Experiment kanban

<!-- lead: Method-scoped experiment cards, dependencies, reports, and lifecycle. -->

<div class="media-slot" data-media="kanban-hero" data-accept="png,jpg,webp,mp4,webm"><p>Media: experiment kanban</p></div>

## How it works

Each method owns a board stored directly under its heading in `project.md`.

| ID | Meaning |
|---|---|
| `backlog` | queued, not started |
| `running` | in progress |
| `done` | completed, with a report expected |
| `successful` | optional successful subset after done |

Cards may have descriptions, tags, dates, milestones, and dependency IDs. Dependencies form a DAG; the board does not duplicate experiments as research-tree nodes.

## How people use the interface

1. Click a method node to open its kanban modal and switch between **Kanban** and **DAG view**.
2. Add a card with +, drag it between columns, double-click to edit, and use ↗ to open its report.
3. In DAG view, drag an arrow from one card to another to add a dependency; double-click an edge to remove it.
4. Filter by dates, tags, or milestones. Closing the modal returns to the map, where the method shows running and completed counts.

## Agent workflows

- `koi-grill-experiment`: interview → report §§1–3 → backlog card.
- `koi-execute-card`: backlog → running immediately, update §3 during work, then running → done before replying.
- `koi-report-review`: review the report and keep column state synchronized.
- `koi-done-research`: save a question, answer, and narrative to `research.json` after done.
- `koi-card-autoresearch`: orchestrate one long card using card execution underneath.
- `koi-prose-style`: keep titles short and details in descriptions.

## Technical details

```markdown
| backlog | running | done | successful |
| --- | --- | --- | --- |
| Title <!-- id:c1 desc:… tags:gpu deps:c0 created:… updated:… --> | | |
```

The parser and writer preserve metadata comments. The client handles dragging, filters, DAG edges, and report links. `research.json` links findings by `method_id` and `card_id`; the run monitor reads live artifacts for running cards.

Related: [Research tree](research-tree.html) · [Architecture](index.html) · [Run monitor](monitor.html) · [Knowledge base](knowledge.html)
