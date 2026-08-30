# Run monitor

<!-- lead: Live logs, metrics, and progress notes for cards in progress. -->

<div class="media-slot" data-media="monitor-hero" data-accept="png,jpg,webp,mp4,webm"><p>Media: run monitor</p></div>

## How it works

A running card can include three report hints:

```text
live_log: path/to/run.log
metrics_dir: path/to/metrics
live_note: training epoch 4 of 20
```

| Hint | Opens |
|---|---|
| `live_log:` | A bounded tail of a text log |
| `metrics_dir:` | Images from a directory, prioritizing known names such as `dashboard.png` |
| `live_note:` | One line describing current activity |

The server resolves safe paths, reads a snapshot, and returns text plus artifact URLs. The UI polls snapshots; no separate event stream is required.

## How people use the interface

1. Open a method kanban. A running card with hints has a **Live monitor** eye button.
2. The modal lists running cards, including cards from other laboratory projects, and keeps card tabs open while you navigate sections.
3. View the progress note, log tail, and metric images; the status line shows snapshot time.
4. Activity overlays on method nodes reflect the same kanban state but do not replace the monitor.

## Agent workflows

- `koi-execute-card` writes and updates the three hints and §3 checkboxes.
- `koi-card-autoresearch` maintains the pulse and note; Manager designs the live view and Debugger reads the log.
- `koi-grill-experiment` decides where logs and charts will be written during specification.

## Technical details

- `GET …/boards/{board}/cards/{card}/live?tail_lines=…` returns one card snapshot.
- `GET …/projects/{id}/kanban/live-monitor` lists monitor candidates.
- `GET …/projects/{id}/live/file?path=…` serves an allowed artifact.
- Remote jobs must write or synchronize logs and images to storage visible to local ResearcherOS.
- Paths outside the repository and its parent are rejected. Log size, line count, and image count are bounded in `live_artifacts.py`.

Related: [Experiment kanban](kanban.html) · [Research tree](research-tree.html) · [Architecture](index.html) · [Knowledge base](knowledge.html)
