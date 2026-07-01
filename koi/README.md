# KOI package layers

```
koi/
  core/       Pure domain — models, markdown I/O, project migrations
  adapters/   Workspace paths, filesystem stores, git sync, agent backends
  services/   Use-cases — knowledge, literature, review, paper, programs, agent chat
    review/     Paper review agent (arxiv, analysis, pipeline)
  *.py        Compatibility shims (`from koi.models` → `koi.core.models`)
```

**Dependency rule:** `core` has no imports from `adapters` or `services`.
`adapters` may use `core`. `services` may use `core` and `adapters`.

New code should import from layered paths (`koi.core.models`, `koi.adapters.workspace`, …).
