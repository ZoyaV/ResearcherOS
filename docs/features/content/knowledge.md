# Knowledge base

<!-- lead: Generated indexes, structured findings, curated documents, and provenance. -->

<div class="media-slot" data-media="knowledge-hero" data-accept="png,jpg,webp,mp4,webm"><p>Media: knowledge base</p></div>

## How it works

The knowledge base combines verdicts from the research tree, structured findings from `research.json`, reports, and curated Markdown.

| Layer | Location | Writer |
|---|---|---|
| Generated | `KNOWLEDGE.md`, `knowledge/hypotheses.md`, `KNOWLEDGE_LOG.md` | `koi/knowledge/` when a project is saved |
| Curated | `knowledge/<topic>.md`, except `hypotheses.md` | a person or curator workflow |

Generated files are indexes and must not be edited by hand. Curated documents keep interpretation, contradictions, limits, and open questions with links to evidence.

## How people use the interface

1. Click **Knowledge** in the workspace toolbar.
2. The Base tab shows supported/refuted/open counts, findings, documents, reports, verdict progress, hypothesis cards, and recent log entries.
3. Open a document or report in the same modal and use breadcrumbs to return.
4. The **Update log** tab displays the complete `KNOWLEDGE_LOG.md`.
5. In files, begin at `KNOWLEDGE.md`; edit only your own `knowledge/*.md` topics.

## Agent workflows

- `koi-done-research` writes question, answer, narrative, certainty, and importance to `research.json`.
- `koi-knowledge-curator` synthesizes multiple experiments into curated topic documents without touching generated files.
- `koi-report-review` and report ingestion can apply a verdict, insights, and done status from a valid report.
- `koi-prose-style` keeps findings and curated notes readable.
- `koi-agent-chat` answers from accumulated findings before scanning reports.

## Technical details

```text
koi-structure/
├── KNOWLEDGE.md
├── KNOWLEDGE_LOG.md
├── research.json
├── knowledge/
│   ├── hypotheses.md
│   └── <curated-topic>.md
└── reports/
```

API endpoints provide the Markdown index, dashboard summary JSON, log, individual files, and knowledge assets. Kanban supplies completed cards and reports; the tree supplies cause verdicts; findings attach to methods through `method_id`. Hub publishes a read-only snapshot.

Related: [Experiment kanban](kanban.html) · [Run monitor](monitor.html) · [Research tree](research-tree.html) · [Architecture](index.html) · [Research Chat](chat.html)
