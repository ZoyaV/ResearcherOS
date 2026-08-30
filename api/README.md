# KOI HTTP API

A thin layer over `koi/`. Entry point: `api.main:app`.

```
api/
  main.py       # FastAPI app, CORS, startup, router registration
  deps.py       # shared helpers (get_project, enqueue_sync, …)
  schemas.py    # Pydantic request bodies
  routers/
    meta.py       # /health, /meta/node-types
    library.py    # /library/*, /agent/translate-to-english
    programs.py   # /laboratory, /programs/*, /projects/grouped
    projects.py   # /projects/* (tree, kanban, reports)
    knowledge.py  # /projects/{id}/knowledge/*
    paper.py      # /projects/{id}/paper/*
    review.py     # paper-reviews, review-agent, paper-question-agent
    agents.py     # /agent-chat*, /settings*, /agent/backends
    sync.py       # /sync/*
```

All unprefixed routes preserve compatibility with the existing UI (`web/api.js`).
