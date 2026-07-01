# ADR-001: Project discovery via `koi-structure/`

## Status

Accepted (2026-06-22)

## Context

Research OS previously stored all projects under a monolithic `koi-workspace/projects/<id>/`
tree. Research data should live alongside project code in separate repositories.

## Decision

1. **Project marker:** `<repo>/koi-structure/project.md`
2. **Discovery:** scan sibling directories of the engine (`parent(ENGINE_ROOT)`), plus
   optional `KOI_SCAN_ROOTS` (comma-separated paths).
3. **Project id:** frontmatter `id` in `project.md` (not the folder name).
4. **Programs:** only `programs:` in project frontmatter; no `programs/` or
   `laboratory.md` files required.
5. **Git sync:** optional `git_repo: true` in project frontmatter — only such
   projects participate in `koi-project-sync` (must also have `.git` in repo root).
   Default is local-only (discovered in UI, not committed).
6. **Runtime:** `.run/` lives in `ENGINE_ROOT/.run/`, not in project repos.
7. **Legacy:** `koi-workspace/` is kept for history; engine does not read
   `koi-workspace/projects/`. Library CSV may fall back to `koi-workspace/library/`
   during transition.

## Layout

```
research_os_dev/
├── ReseachOS/           # engine
├── koi-workspace/       # legacy (not scanned for projects)
└── mmrl_problem/        # example project repo (local; git_repo defaults false)
    ├── koi-structure/
    └── projectcode/
```

Example with git: `bicycle_problem/` has `git_repo: true` and its own `.git`.

## Onboarding paths

1. **Attach:** add `koi-structure/` to an existing sibling repo (agent or API).
2. **Create:** UI/API creates `<slug>/koi-structure/` as a sibling of the engine.

## Consequences

- All project path resolution goes through `ProjectMount` (`koi/adapters/project_mount.py`).
- `create_project()` writes a new sibling directory, not `koi-workspace/projects/`.
- Laboratory view is synthesized at runtime from discovered projects.
