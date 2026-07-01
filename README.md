# ResearchOS

## Коротко о проекте

**ResearchOS** — платформа для организации исследований. Её методология строится вокруг **извлечения знаний**: от проблемы и дерева гипотез — через канбан экспериментов и структурированные отчёты — к вердиктам и инсайтам, которые накапливаются в базе знаний по заданным правилам.

Цикл исследования:

```
Проблема → причины (гипотезы о природе) → гипотезы (как доказать / устранить)
  → методы проверки → карточки-эксперименты в канбане
  → отчёт → вердикт + инсайты → база знаний
```

Данные хранятся в **Markdown-файлах**, без базы данных. **Engine** — код в этом репозитории (`koi/`, `api/`, `web/`, `standards/`, `agent/`). **Проекты** — соседние каталоги с маркером `koi-structure/project.md`; код экспериментов — в `projectcode/` рядом.

Подробный путеводитель для новичка: [docs/human/getting-started.md](docs/human/getting-started.md).  
Инструкции для агента IDE: [agent/AGENTS.md](agent/AGENTS.md).

---

## Начало работы

### 1) Как установить

#### Инструкция

**Требования:** Python 3.10+, `git`, `curl`. Опционально: [tectonic](https://tectonic-typesetting.github.io) или `pdflatex` — для PDF статей.

```bash
# Клонировать репозиторий
git clone <url-репозитория-ResearchOS> ReseachOS
cd ReseachOS

# Запустить API (8010) и UI (8080) одной командой
./scripts/koi-serve.sh start

# Проверить
./scripts/koi-serve.sh status
```

Открыть в браузере:

| Сервис | URL |
|--------|-----|
| Веб-интерфейс | http://127.0.0.1:8080 |
| API (Swagger) | http://127.0.0.1:8010/docs |

Скрипт сам создаст `.venv`, установит зависимости из `requirements.txt` и при необходимости скачает tectonic в `.tools/tectonic`.

**Управление сервером:**

```bash
./scripts/koi-serve.sh start    # поднять
./scripts/koi-serve.sh stop     # остановить
./scripts/koi-serve.sh restart  # перезапустить
./scripts/koi-serve.sh status   # статус
```

**Настройки и ключи** (Cursor API и др.) — через кнопку «Настройки» в UI или файл `.env` в корне `ReseachOS/` (в git не попадает).

**Ручной запуск** (два терминала, если нужен контроль):

```bash
cd ReseachOS
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn api.main:app --reload --host 127.0.0.1 --port 8010
```

```bash
cd ReseachOS/web && python3 -m http.server 8080
```

При работе в Cursor с открытым workspace ResearchOS сервер поднимается автоматически через `.cursor/hooks.json`.

#### Промпт для агента (установка)

Скопируйте в чат агента в Cursor / Claude Code:

```
Установи и запусти ResearchOS в этом репозитории.

1. Проверь, что есть Python 3.10+ и git.
2. Из корня ReseachOS выполни: ./scripts/koi-serve.sh start
3. Дождись health на http://127.0.0.1:8010/health и открой UI http://127.0.0.1:8080
4. Если порты заняты — сообщи и предложи альтернативные (см. docs/human/getting-started.md §2).
5. При ошибках зависимостей — создай .venv и pip install -r requirements.txt, затем повтори start.

Не меняй git config. Не коммить .env.
```

---

### 2) Как создать проект

Есть два пути: **присоединить существующий репозиторий** (рекомендуется для кода экспериментов) или **создать через интерфейс**.

#### в1) Проект рядом с ResearchOS (файловая структура)

ResearchOS при старте сканирует **родительский каталог** engine'а и находит все п
PaperVPN
error-connection-configuration-fetchапки с `koi-structure/project.md`. Дополнительные корни — через `KOI_SCAN_ROOTS=/path/a,/path/b`.

Целевая раскладка:

```
research_os_dev/              # общий родитель (имя любое)
├── ReseachOS/                # engine (этот репозиторий)
├── bicycle_problem/          # пример: git_repo: true
│   ├── koi-structure/        # ← ResearchOS читает и пишет сюда
│   │   ├── project.md        # дерево гипотез + канбан
│   │   ├── research.json     # выводы по экспериментам
│   │   ├── reports/          # отчёты карточек
│   │   └── knowledge/        # курируемые документы БЗ
│   ├── projectcode/          # ← код экспериментов
│   └── .git/                 # опционально, если git_repo: true
└── my_new_project/
    ├── koi-structure/
    └── projectcode/
```

**Минимальные шаги вручную:**

1. Создайте папку-соседа, например `research_os_dev/my_new_project/`.
2. Внутри — `koi-structure/project.md` с frontmatter (`id`, `title`, `format: koi/1`) и узлом `problem`.
3. Создайте `projectcode/` для скриптов экспериментов.
4. Перезапустите API или вызовите rescan — проект появится в сайдбаре UI.

Формат `project.md`: [docs/human/project-format.md](docs/human/project-format.md).  
ADR по discovery: [docs/agent/adr-001-project-discovery.md](docs/agent/adr-001-project-discovery.md).

**Git-синхронизация** (опционально): в frontmatter `project.md` добавьте `git_repo: true` и инициализируйте `.git` в корне репозитория проекта. Тогда сработает скилл `koi-project-sync`.

##### Промпт для агента (интегрирующая папка)

```
Создай новый исследовательский проект ResearchOS рядом с engine.

Контекст:
- Engine: ReseachOS/ (этот репозиторий)
- Родитель: parent(ReseachOS)/
- Маркер проекта: <имя_папки>/koi-structure/project.md
- Код экспериментов: <имя_папки>/projectcode/

Задача:
1. Спроси у меня название проблемы и желаемый тег папки (латиница, например mmrl_problem).
2. Создай sibling-каталог parent(ReseachOS)/<тег>/ с:
   - koi-structure/project.md — frontmatter (id, title, format: koi/1), корневой узел problem
   - koi-structure/research.json — {"version":1,"questions":[]}
   - projectcode/README.md — заглушка для кода
3. Не трогай ReseachOS/.venv и не коммить без явной просьбы.
4. После создания — ./scripts/koi-serve.sh restart (или скажи перезагрузить страницу UI).

Если папка уже существует — предложи attach: только добавить koi-structure/ в существующий репозиторий.
```

#### в2) Создание через интерфейс

1. Откройте http://127.0.0.1:8080.
2. Слева — шеврон `<` / `>`: раскрывает **сайдбар проектов**.
3. Внизу сайдбара — **«+ Новый проект»**.
4. В модалке заполните:
   - **Название** — формулировка проблемы;
   - **Описание** — краткий контекст;
   - **Тег** — имя папки проекта (`mmrl_problem`, латиница, без пробелов);
   - **Программа** — существующая, новая или «без программы».
5. Нажмите **«Создать»**.

UI создаст sibling-каталог `parent(ReseachOS)/<тег>/` с `koi-structure/` и `projectcode/` автоматически. На карте появится узел «Проблема».

**Где писать код:** в `projectcode/` созданного репозитория (не в `koi-structure/`).  
**Где вести исследование:** дерево гипотез и канбан — в UI или в `koi-structure/project.md`; отчёты — `koi-structure/reports/`; выводы — `koi-structure/research.json`.

**Дальнейшие шаги в UI:**

| Действие | Где в интерфейсе |
|----------|------------------|
| Добавить причину / гипотезу / метод | Пунктирный кружок «Добавить +» под узлом на карте |
| Редактировать узел | Клик по узлу → «Редактировать» |
| Завести эксперимент | Клик по методу → канбан → «+» в колонке |
| Написать отчёт | Клик по карточке канбана → редактор отчёта |
| Спросить агента | Панель узла или кнопка чата в workspace |
| База знаний | Кнопка «База знаний» в нижней панели |
| Related Work | Ссылка «RelatedWork» → `literature.html` |
| Статья (NeurIPS PDF) | Кнопка «Статья» в нижней панели |

Эталонный заполненный проект для ориентира — **«Пример: решение квадратных уравнений»** в сайдбаре (см. [getting-started.md](docs/human/getting-started.md) §0).

---

## Возможности системы

### 1) Интерфейс

| Раздел | Что делает |
|--------|------------|
| **Карта гипотез** | Радиальное дерево: problem → cause → cause_evidence / remediation → method; бейджи вердиктов ✔/✗ |
| **Канбан** | У каждого метода — колонки backlog / running / done; карточки = эксперименты |
| **Отчёты** | Редактор по клику на карточку; шаблон с id узлов и датой; вложения в `reports/.../assets/` |
| **База знаний** | Оглавление вердиктов, инсайтов, документов; журнал пополнений |
| **Related Work** | Поиск по библиотеке (`library/library.csv`), обзор статей, кластеры ответов на исследовательский вопрос |
| **Статья** | Сборка NeurIPS preprint (LaTeX → PDF) из всего графа проекта |
| **Чат с агентом** | Вопросы из UI → очередь агента; быстрый ответ из `research.json`, если совпадение точное |
| **Открытия** | Колокольчик — новые ответы на исследовательские вопросы в `research.json` |
| **Синхронизация** | Кнопка sync — git pull/push для проектов с `git_repo: true` |
| **Режимы View** | Chief researcher / Team lead / Researcher — только представление, не права |
| **О платформе** | Интерактивный тур: `web/tour.html` |

### 2) Автоматические функции

| Функция | Когда срабатывает | Результат |
|---------|-------------------|-----------|
| **Discovery проектов** | Старт API | Находит `*/koi-structure/project.md` в sibling-каталогах |
| **Интеграция отчёта** | `koi_check_hypothesis.py --ingest-only` или сохранение валидного `.run.md` | Вердикт на cause, инсайты в `research.json`, карточка → done, пересборка БЗ |
| **Автоген БЗ** | После save / ingest | `KNOWLEDGE.md`, `knowledge/hypotheses.md`, `KNOWLEDGE_LOG.md` |
| **Очередь done-research** | Карточка переехала в done | Формулировка question/narrative в `research.json` (скилл `koi-done-research`) |
| **Очередь agent-chat** | Вопрос из UI | Ответ агента в панели чата (скилл `koi-agent-chat`) |
| **Очередь paper** | «Сгенерировать статью» | LaTeX + PDF в `koi-structure/paper/` (скилл `koi-paper`) |
| **Очередь related-work** | Запрос на `literature.html` | Markdown-обзор в проекте (скилл `koi-related-work`) |
| **Git sync** | Хуки Cursor, кнопка sync, после значимых изменений | commit + push / pull для проектов с `git_repo: true` |
| **Хуки сессии** | Открытие / закрытие workspace в Cursor | Подъём сервера, pull, разбор очередей |
| **Установка tectonic** | `koi-serve.sh start`, если нет LaTeX | Бинарь в `.tools/tectonic` |

Детерминированные правила (без LLM): `koi/services/report_ingest.py`, `agent/bin/build_kb.py`.

### 3) Реализованные скилы

Плейбуки лежат в `.cursor/skills/*/SKILL.md`. Они не привязаны к Cursor — агент читает их как обычные инструкции.

| Скилл | Назначение | Как работает (кратко) |
|-------|------------|------------------------|
| **koi-execute-card** | Выполнение карточки канбана | Читает карточку → ведёт чеклист подзадач в отчёте → `running` → `done` → затем `koi-done-research` |
| **koi-done-research** | Вывод по завершённому эксперименту | Очередь `.run/done-research-queue.json`; читает отчёт → пишет question/answer/certainty в `research.json` |
| **koi-report-review** | Ревью отчётов | 4 readonly-критика (стиль, постановка, подзадачи, результаты) до сохранения `.md` / `.run.md` |
| **koi-prose-style** | Человекочитаемый текст | Ревью заголовков узлов, карточек, narrative — subagent PASS перед записью |
| **koi-agent-chat** | Ответы из UI | Очередь `.run/agent-chat-queue.json`; сначала `research.json`, потом отчёты |
| **koi-knowledge-curator** | Глубокая суммаризация БЗ | Кросс-анализ инсайтов → курируемые `knowledge/<тема>.md` |
| **koi-project-sync** | Git sync проектов | Pull при старте сессии; commit+push значимых изменений в `koi-structure/` |
| **koi-paper** | Статья NeurIPS | Очередь `.run/paper-queue.json` → LaTeX из графа → PDF через tectonic |
| **koi-related-work** | Обзор литературы | Очередь `.run/related-work-queue.json` → markdown по библиотеке |
| **koi-visual-qa** | Визуальная проверка UI | Playwright-скриншоты карты, канбана, модалок (dev) |
| **koi-ui-design-review** | Ревью правок `web/` | Линт, a11y, визуальный проход после изменений интерфейса |

**Типичный цикл агента** (см. [agent/AGENTS.md](agent/AGENTS.md)):

1. При старте — проверить очереди: `koi_done_research.py pending`, agent-chat, paper, related-work.
2. Выполнить карточку — **koi-execute-card** → отчёт по `agent/templates/experiment-report.md`.
3. Интегрировать — `python scripts/koi_check_hypothesis.py <project> <card> --ingest-only`.
4. При необходимости — **koi-report-review** для публичного отчёта, **koi-prose-style** для текстов в UI.

---

## Контакты

| | |
|---|---|
| Документация | [docs/human/](docs/human/) · [docs/agent/](docs/agent/) |
| Вопросы по платформе | *добавьте контакт команды* |
| Баги и предложения | *добавьте issue tracker / email* |
