# ResearcherOS docs-site

English-language docs site: project overview, three ways to get started, skill catalog, lessons, and feature docs (`features/`).

## Run locally

```bash
cd docs-site
python3 scripts/generate_skills.py   # update skills/*.html from skills.json
python3 -m http.server 8765
# http://127.0.0.1:8765/
```

## Deployment

This tree is meant for local browsing (`python3 -m http.server`). External hosting and repository URLs are not wired in this anonymous build.

## Update a skill

1. Edit `skills.json` (description, Mermaid diagram, and example).
2. `python3 scripts/generate_skills.py`
3. Commit `skills.json` and the generated `skills/*.html` files.
