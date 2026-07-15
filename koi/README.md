# KOI package layers

```
koi/
  core/       Pure domain — models, markdown I/O, project migrations
  adapters/   Workspace paths, filesystem stores, git sync, agent backends
  projects/   Project capability — commands, views, reports, live, kanban, sync
  laboratory/ Cross-project programs and portfolio views
  application/ Cross-feature use-cases and temporary project compatibility shims
  services/   Remaining use-cases — knowledge, literature, review, paper, agent chat
    review/     Paper review agent (arxiv, analysis, pipeline)
  *.py        Temporary external compatibility shims
```

**Dependency rule:** `core` has no imports from `adapters`, `projects`, or `services`.
`adapters` may use `core`. Feature packages such as `projects` coordinate `core`,
`adapters`, and established services behind a capability-specific interface.

Bundled code must import from canonical paths (`koi.core.models`,
`koi.projects.commands`, …); `tests/test_architecture.py` enforces this rule.
The root and `koi.application` project shims remain only for external compatibility
and can be removed after an explicit compatibility decision.
