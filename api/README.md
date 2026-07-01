# KOI HTTP API

Тонкий слой над `koi/`. Точка входа: `api.main:app`.

```
api/
  main.py       # FastAPI app, CORS, startup, подключение роутеров
  deps.py       # общие хелперы (get_project, enqueue_sync, …)
  schemas.py    # Pydantic-тела запросов
  routers/
    meta.py       # /health, /meta/node-types
    library.py    # /library/*, /agent/translate-to-english
    programs.py   # /laboratory, /programs/*, /projects/grouped
    projects.py   # /projects/* (дерево, kanban, отчёты)
    knowledge.py  # /projects/{id}/knowledge/*
    paper.py      # /projects/{id}/paper/*
    review.py     # paper-reviews, review-agent, paper-question-agent
    agents.py     # /agent-chat*, /settings*, /agent/backends
    sync.py       # /sync/*
```

Все пути без префикса — совместимость с существующим UI (`web/api.js`).
