# Features docs (`docs/features`)

A separate page set describing ResearcherOS architecture and local features.

The style matches ResearcherOS (Outfit/Syne and the same tokens). `css/features.css` is self-contained. These pages are not embedded in the product yet; edit them here and view them locally.

## Run locally

```bash
cd ReseachOS/docs/features
python3 -m http.server 8766
# http://127.0.0.1:8766/
```

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
| `media/` | Images and videos supplied separately |
| `css/`, `js/` | Shared section shell |

## Contents

1. **Overview** — three layers: Research Project · Local · Hub, plus the diagram.
2. **Local feature catalog** — eight pages, from the tree through widgets.
3. **Feature page pattern** — media → how it works → UI → agent workflows → technical details.

Content is Markdown under `content/`; media belongs under `media/`.
