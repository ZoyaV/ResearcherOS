# Evo headless backend

Use the ResearchOS Evo adapter when a card needs code search with multiple
candidate branches. Start Evo in the project code root, not in
`tree/<repo>/koi-structure`.

Required artifacts:

```text
projectcode/runs/evo/<run_id>/state.json
projectcode/runs/evo/<run_id>/experiments.json
projectcode/runs/evo/<run_id>/stdout.log
projectcode/runs/evo/<run_id>/traces/
```

Put `evo_run: runs/evo/<run_id>` and `live_log:` into the card description so
the existing ResearchOS Monitor exposes the Evo pane. Keep train score and
held-out test score as separate fields; only the held-out score may support the
experiment verdict.
