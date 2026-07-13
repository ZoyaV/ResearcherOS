# ResearchOS — 10 ключевых фич (для персонализации писем)

Сравнение с: Notion/Obsidian (заметки), LabArchives/Benchling (ELN), MLflow/W&B (ML-эксперименты), GitHub/GitLab (код), Overleaf (отчёты), ChatGPT/Claude Projects (ИИ-ассистенты).

## F1. Дерево гипотез «Science Agile»

**Суть:** problem → cause → evidence/remediation → method → эксперименты. Не список задач, а проверяемые утверждения с вердиктами.

**Отличие от других:** Notion/Jira — иерархия задач без логики «гипотеза → доказательство → вердикт». ELN — журнал экспериментов без связи с деревом причин.

**Детали:** UI не даёт создать узел не того типа. Вердикты (`open|supported|refuted`) живут на cause-узлах. Карта гипотез визуализирует весь исследовательский контекст.

---

## F2. Предрегистрация правила решения

**Суть:** до прогона фиксируется «гипотеза подтверждена, если метрика X ≥ порог Y»; вердикт — подстановка чисел, не «по впечатлению».

**Отличие:** W&B/MLflow логируют метрики постфактум; preregistration в OSF — отдельный документ, не связанный с канбаном и БЗ.

**Детали:** Правило в описании cause/method и в §2 отчёта. Ingest отбраковывает отчёт без §5.1 вердикта и §5.2 JSON инсайтов.

---

## F3. Markdown без базы данных

**Суть:** `project.md`, `research.json`, `reports/`, `knowledge/` — всё в git-friendly файлах. UI = редактор markdown.

**Отличие:** Benchling/LabArchives — проприетарные БД. Notion — облако без git-истории.

**Детали:** Один проект = папка. Нет vendor lock-in на хранилище. Orphan-branch sync для разделения кода и `koi-structure/`.

---

## F4. Автоматическая база знаний (детерминированная)

**Суть:** `KNOWLEDGE.md`, `hypotheses.md`, `KNOWLEDGE_LOG.md` пересобираются при сохранении проекта — без LLM.

**Отличие:** RAG/ChatGPT «помнит» через эмбеддинги с галлюцинациями. ResearchOS — детерминированный diff из вердиктов и инсайтов.

**Детали:** ≤3 инсайта на метод (вопрос-ответ с числами). Журнал пополнений. Глобальный индекс `agent/KNOWLEDGE.md`.

---

## F5. Канбан на уровне метода

**Суть:** Backlog → Running → Done (+ Successful) привязан к узлу method; карточка = один эксперимент с отчётом.

**Отличие:** Jira/Trello — задачи без привязки к гипотезе. MLflow — runs без канбан-планирования.

**Детали:** Live card view, done-research очередь, subagent-ревью отчётов (koi-report-review).

---

## F6. ИИ-агенты как штатные исследователи

**Суть:** AGENTS.md + skills: агент проводит эксперимент, пишет `.run.md`, ingest → вердикт + инсайты.

**Отличие:** Copilot/Cursor «помогают с кодом», но не встроены в цикл гипотеза→вердикт→БЗ. AutoGPT — без научной дисциплины.

**Детали:** koi-execute-card, koi-done-research, koi-agent-chat (вопросы из UI), koi-knowledge-curator.

---

## F7. Composite view (мульти-репозиторное дерево)

**Суть:** проекты с одним `composite_id` сливаются в одно дерево на чтение; запись — в owning repo.

**Отличие:** Git submodules/monorepo — ручная синхронизация. Нет аналога в ELN/Notion для распределённых команд.

**Детали:** ADR-002, виртуальная программа в sidebar, conflict detection.

---

## F8. Программы и лаборатория

**Суть:** `laboratory.md` → `programs/` → `projects/` — стратегический слой над проектами.

**Отличие:** GitHub Organizations — группировка репо без исследовательской семантики. Confluence — wiki без вердиктов.

**Детали:** Проект в нескольких программах. Program summary с агрегатами по вердиктам.

---

## F9. Vendor-neutral интеграция агентов

**Суть:** Cursor, Claude Code, inbox-режим — смена бэкенда без смены методологии и данных.

**Отличие:** OpenAI Assistants / Claude Projects — привязка к одному провайдеру. ResearchOS — данные и процесс независимы от модели.

**Детали:** `GET /agent/backends`, agent-chat queue, skills не Cursor-специфичны.

---

## F10. Open Source и культура воспроизводимости

**Суть:** публичные отчёты по skeleton, no-ai-report-rules, community вокруг engine + demo projects.

**Отличие:** Проприетарные ELN. Closed AI research tools. ResearchOS — engine на GitHub, методология переносима.

**Детали:** standards/templates, paper review bundles, onboarding tour, bicycle_problem demo.
