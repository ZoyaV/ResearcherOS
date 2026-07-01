<p align="center">
  <img src="docs/assets/researchos-logo.png" alt="ResearchOS" width="480">
</p>

# ResearchOS

## About

ResearchOS is a research organization platform built around knowledge extraction: from a problem and hypothesis tree, through kanban experiments and structured reports, to verdicts and insights that accumulate in a curated knowledge base.

```
Problem → causes (nature hypotheses) → hypotheses (how to prove / fix)
  → verification methods → kanban experiment cards
  → report → verdict + insights → knowledge base
```

All research data lives in Markdown files — no database required. The engine is this repository (`koi/`, `api/`, `web/`, `standards/`, `agent/`). Projects are sibling directories marked by `koi-structure/project.md`; experiment code lives in `projectcode/` (or a custom `code_root`).

| Docs | |
|------|---|
| Getting started walkthrough | [docs/human/getting-started.md](docs/human/getting-started.md) |
| Project format | [docs/human/project-format.md](docs/human/project-format.md) |
| Agent instructions | [agent/AGENTS.md](agent/AGENTS.md) |

## News

| Date | What shipped |
|------|----------------|
| 2026-07-01 | Open-source release on GitHub (`main` = engine, `test_project` = demo sample). |
| 2026-07-01 | Orphan-branch sync — `koi-structure/` can live on a dedicated git branch (`koi/research` or custom) while your code branch stays clean. CLI: `scripts/koi_project_sync.py init-sync-branch`. |
| 2026-07-01 | Stable local serve — `koi-serve.sh` works reliably on macOS; web port proxies `/api` so one URL is enough. |
| 2026-07-01 | Live card view — real-time experiment activity on kanban cards; refreshed method-activity UI. |
| 2026-07-01 | Report & knowledge fixes — reliable card report loading; repo `docs/*.md` served via knowledge API. |
| 2026-06-23 | Demo project — `bicycle_problem` sample (search-ad budget efficiency) for onboarding. |

## Installation

Requirements: Python 3.10+, `git`, `curl`. Optional: [tectonic](https://tectonic-typesetting.github.io) or `pdflatex` for NeurIPS PDF export.

### Clone

```bash
git clone git@github.com:ZoyaV/ReseacherOS.git ReseachOS
cd ReseachOS
```

### Option A — conda (recommended)

```bash
conda create -n researchos python=3.11 -y
conda activate researchos
pip install -r requirements.txt
pip install -r requirements-dev.txt   # optional, for tests
```

### Option B — venv

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### Start

```bash
./scripts/koi-serve.sh start
./scripts/koi-serve.sh status
```

| Service | URL |
|---------|-----|
| Web UI | http://127.0.0.1:8080 |
| API (Swagger) | http://127.0.0.1:8010/docs |

`koi-serve.sh` creates `.venv` if missing, installs dependencies, and downloads tectonic to `.tools/tectonic` when needed.

```bash
./scripts/koi-serve.sh stop      # stop
./scripts/koi-serve.sh restart  # restart
```

Settings and API keys — Settings button in the UI, or `.env` in the repo root (gitignored; see `.env.example`).

### Try the demo project

The sample project lives on orphan branch `test_project`. Check it out as a sibling worktree:

```bash
cd ..                              # parent of ReseachOS/
git -C ReseachOS worktree add bicycle_problem test_project
./ReseachOS/scripts/koi-serve.sh restart
```

Open http://127.0.0.1:8080 — `bicycle_problem` appears in the sidebar.

## Add a project

ResearchOS scans the parent directory of the engine and discovers every folder with `koi-structure/project.md`. Extra roots: `KOI_SCAN_ROOTS=/path/a,/path/b`.

```
workspace/                    # any parent folder name
├── ReseachOS/                # engine (this repo)
├── my_experiment/            # your project
│   ├── koi-structure/        # ← ResearchOS reads/writes here
│   │   ├── project.md        # hypothesis tree + kanban
│   │   ├── research.json     # experiment conclusions
│   │   ├── reports/            # card reports
│   │   └── knowledge/          # curated KB docs
│   ├── projectcode/          # ← experiment code
│   └── .git/                 # your project repo
└── bicycle_problem/          # demo (optional worktree)
```

### Attach an existing code repository

Use this when you already have a git repo with experiment code and want ResearchOS to manage `koi-structure/` on a separate orphan branch.

Layout: clone or place your repo as a sibling of `ReseachOS/`. Add `koi-structure/project.md` (minimal frontmatter below).

Agent prompt — paste into Cursor / Claude Code; the agent should read skill `koi-project-sync` and run the CLI:

```
Attach my existing experiment repo to ResearchOS with orphan-branch sync.

Context:
- Engine: ../ReseachOS/ (or absolute path to this ResearchOS clone)
- My project repo: <path> (sibling of ReseachOS/)
- Research data: <repo>/koi-structure/
- Experiment code: <repo>/projectcode/ (or existing code paths)

Steps:
1. Ask me for: project title, folder/repo name, and preferred sync branch name
   (default: koi/research).
2. Create koi-structure/project.md with frontmatter:
   id, title, format: koi/1, git_repo: true, git_sync_branch: <branch>
   Plus koi-structure/research.json: {"version":1,"questions":[]}
3. If the tree is empty, interview me briefly and draft a minimal problem → cause → method skeleton.
4. From ReseachOS root, run:
   python scripts/koi_project_sync.py init-sync-branch --project-id <id>
   This creates the orphan branch on origin and seeds koi-structure/.
5. On the CODE branch of my project repo:
   - git rm -r --cached koi-structure  (if it was tracked)
   - append to .gitignore:
     koi-structure/
     .koi-sync-worktree/
     .koi-sync-bootstrap/
   - commit: "chore: track koi-structure on orphan sync branch"
6. Verify: python scripts/koi_project_sync.py status
7. Restart serve: ./scripts/koi-serve.sh restart
8. Do not change git config. Do not commit secrets (.env).

If init-sync-branch reports "exists", the remote branch is already there — see next section.
```

Manual CLI (same result):

```bash
cd ReseachOS
python scripts/koi_project_sync.py init-sync-branch --project-id <your-project-id>
```

### Sync branch already exists

If someone on your team (or CI) already created the orphan branch — e.g. `koi/research`, `test_project`, or a custom name — you only need to point your code branch at it.

In `koi-structure/project.md` on your working branch:

```yaml
---
id: my-project
title: My Research Problem
format: koi/1
git_repo: true
git_sync_branch: koi/research    # ← must match the existing orphan branch
---
```

Then pull research data into your working tree:

```bash
cd ReseachOS
python scripts/koi_project_sync.py pull --project-id my-project
```

Ongoing sync: UI Sync button, skill `koi-project-sync`, or:

```bash
python scripts/koi_project_sync.py push --project-id my-project
python scripts/koi_project_sync.py pull --project-id my-project
```

### Start from scratch (no repo yet)

#### Option 1 — Agent interview

Paste into your IDE agent:

```
Create a new ResearchOS project from scratch.

1. Interview me: research problem, domain, what we already know, what experiments are feasible.
2. Propose a hypothesis tree: problem → causes → evidence/remediation hypotheses → methods.
3. Ask for a folder tag (latin slug, e.g. protein_folding).
4. Create sibling directory parent(ReseachOS)/<tag>/ with:
   - koi-structure/project.md (frontmatter + tree nodes)
   - koi-structure/research.json
   - projectcode/README.md
5. If I want git sync, init a git repo there, set git_repo: true, run init-sync-branch.
6. Restart ./scripts/koi-serve.sh and tell me to open the UI.

Follow koi-prose-style for all user-facing text. Do not commit without my explicit ask.
```

#### Option 2 — Build the tree in the UI

1. Open http://127.0.0.1:8080
2. Expand the project sidebar (`<` / `>` chevron)
3. Click "+ New project"
4. Fill in: Title, Description, Tag (folder name), Program
5. Click Create

The UI creates `parent(ReseachOS)/<tag>/` with `koi-structure/` and `projectcode/` automatically. A Problem node appears on the map.

| Next step | Where |
|-----------|-------|
| Add cause / hypothesis / method | Dashed "+" under a node on the map |
| Edit a node | Click node → Edit |
| Create an experiment | Click method → kanban → + in a column |
| Write a report | Click kanban card → report editor |
| Ask the agent | Node panel or workspace chat button |

Where to write code: `projectcode/` (not inside `koi-structure/`).  
Where research lives: tree + kanban in UI or `koi-structure/project.md`; reports in `koi-structure/reports/`.

## Platform overview

| Area | Highlights |
|------|------------|
| Hypothesis map | Radial tree: problem → cause → evidence / remediation → method |
| Kanban | Per-method backlog / running / done columns |
| Reports | Structured experiment reports with ingest → verdicts + insights |
| Knowledge base | Auto-built from reports; curator skill for deep synthesis |
| Related work | Literature search and review generation |
| Paper export | NeurIPS LaTeX → PDF from the full project graph |
| Agent skills | `.cursor/skills/koi-*` — card execution, sync, review, chat, paper |

## Links

| | |
|---|---|
| Documentation | [docs/human/](docs/human/) · [docs/agent/](docs/agent/) |
| Issues | [github.com/ZoyaV/ReseacherOS/issues](https://github.com/ZoyaV/ReseacherOS/issues) |
