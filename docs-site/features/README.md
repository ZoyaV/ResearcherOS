# Features docs (`docs-site/features`)

Architecture and local feature catalog for ResearcherOS.

## Run locally

```bash
cd docs-site
python3 -m http.server 8765
# http://127.0.0.1:8765/features/
```

External deploy URLs are not wired in this anonymous build.

## Structure

| Path | Purpose |
|------|------------|
| `index.html` + `content/overview.md` | Architecture overview |
| `research-tree.html` + `content/research-tree.md` | Research tree |
| `kanban.html` + `content/kanban.md` | Experiment kanban |
| `monitor.html` + `content/monitor.md` | Run monitor |
| `knowledge.html` + `content/knowledge.md` | Knowledge base |
| `chat.html` + `content/chat.md` | Research Chat |
| `related-work.html` + `content/related-work.md` | Related Work |
| `paper.html` + `content/paper.md` | PaperDraft |
| `widgets.html` + `content/widgets.md` | Widgets |
| `full_schema.html` | Interactive architecture diagram |
| `media/` | Images and videos |
| `css/`, `js/` | Section shell |

Content is Markdown under `content/`; media belongs under `media/`.
