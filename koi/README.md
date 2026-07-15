# KOI package layers

```
koi/
  core/       Pure domain — models, markdown I/O, project migrations
  adapters/   Workspace paths, filesystem stores, git sync, agent backends
  services/   Use-cases — knowledge, literature, review, paper, programs, agent chat
    review/     Paper review agent (arxiv, analysis, pipeline)
  *.py        Temporary external compatibility shims
```

**Dependency rule:** `core` has no imports from `adapters` or `services`.
`adapters` may use `core`. `services` may use `core` and `adapters`.

Bundled code must import from canonical paths (`koi.core.models`,
`koi.adapters.workspace`, …); `tests/test_architecture.py` enforces this rule.
The root shims remain only for external compatibility and can be removed together
after the feature-package migration and an explicit compatibility decision.
