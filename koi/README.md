# KOI package layers

```
koi/
  core/       Pure domain — models, markdown I/O, project migrations
  adapters/   Workspace paths, filesystem stores, git sync, agent backends
  projects/   Project capability — commands, views, reports, live, kanban, sync
  laboratory/ Cross-project programs and portfolio views
  application/ Cross-feature use-cases and temporary compatibility shims
  services/   Remaining use-cases — knowledge, literature, review, paper, agent chat
    review/     Paper review agent (arxiv, analysis, pipeline)
  *.py        Temporary capability entry points still awaiting migration
```

**Dependency rule:** `core` has no imports from `adapters`, `projects`, or `services`.
`adapters` may use `core`. Feature packages such as `projects` coordinate `core`,
`adapters`, and established services behind a capability-specific interface.

Bundled code must import from canonical paths (`koi.core.models`,
`koi.projects.commands`, …); `tests/test_architecture.py` enforces this rule.
Stabilized root shims for `core`, `adapters`, `projects`, and `laboratory` have been
removed. The remaining root entry points belong to capabilities that have not yet
completed their package migration; bundled code must not import through them.
