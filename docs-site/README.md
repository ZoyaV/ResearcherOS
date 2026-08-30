# ResearcherOS docs-site

Public English-language GitHub Pages site: project overview, three ways to get started, skill catalog, and lessons.

## Run locally

```bash
cd docs-site
python3 scripts/generate_skills.py   # update skills/*.html from skills.json
python3 -m http.server 8765
# http://127.0.0.1:8765/
```

## Deployment

The [`.github/workflows/pages.yml`](../.github/workflows/pages.yml) workflow publishes `docs-site/` to GitHub Pages on pushes to `main`.

Repository setting: **Settings → Pages → Source: GitHub Actions**.

Project URL: `https://zoyav.github.io/ResearcherOS/` (repository name: `ResearcherOS`).

## Update a skill

1. Edit `skills.json` (description, Mermaid diagram, and example).
2. `python3 scripts/generate_skills.py`
3. Commit `skills.json` and the generated `skills/*.html` files.
