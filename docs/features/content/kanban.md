# Канбан экспериментов

<p class="lead">Доска прогонов у каждого метода: колонки, карточки, зависимости между ними и отчёты. Таблица лежит в <code>project.md</code> сразу под узлом метода.</p>

<div class="media-slot" data-media="kanban-hero" data-accept="png,jpg,webp,mp4,webm">
  <strong>Слот для картинки или видео</strong>
  Положите файл в <code>media/kanban-hero.png</code> (или <code>.jpg</code> / <code>.webp</code> / <code>.mp4</code> / <code>.webm</code>).
</div>

## Как работает

Канбан появляется только у узла типа «метод». Одна доска = один способ проверки (доказательство причины или гипотеза устранения). Карточка — один запланированный или идущий эксперимент, не отдельный лист дерева.

Колонки по умолчанию:

| Id | Смысл |
|----|--------|
| <code>backlog</code> | очередь, ещё не начали |
| <code>running</code> | в работе |
| <code>done</code> | закончили, есть (или должен быть) отчёт |
| <code>successful</code> | опционально: «успешные» после <code>done</code> |

Старая колонка <code>planned</code> при загрузке переносится в <code>backlog</code>.

У карточки: заголовок, описание (в т.ч. краткий вывод в колонках завершения), теги, зависимости от других карточек (<code>deps</code> — рёбра DAG), метки времени создания и правки. Отчёт карточки — отдельный Markdown: <code>reports/&lt;метод&gt;/&lt;карточка&gt;.md</code> (индекс в <code>reports/index.json</code>).

Два режима в модальном окне метода: классическая доска (колонки) и вид зависимостей (DAG view). Фильтры: период изменения, теги, вехи (milestones) с привязкой к id карточек. Блок «мастер-отчёты» — страницы уровня метода, не карточки.

Живой монитор прогона (графики, логи) — отдельная фича; открывается для карточек в <code>running</code>. На этой странице — только доска и её связь с отчётом.

## Как человек работает в интерфейсе

1. На карте мыслей кликните узел **метода** (или двойной клик) — откроется модальное окно канбана.
2. В шапке — тип «Метод», заголовок метода (двойной клик правит title в дереве), подсказка жестов.
3. Вкладки **Kanban** / **DAG view**.
4. На доске: «+» в колонке — новая карточка; ручка ⠿ — перетащить между колонками; двойной клик по карточке — правка; ↗ — открыть отчёт. В колонках завершения под заголовком карточки виден краткий вывод (описание).
5. В DAG: зажать стрелку на карточке и отпустить на другой — добавить зависимость; двойной клик по ребру — удалить.
6. Фильтры сверху: даты, теги, сброс. Секция «Вехи» (milestones) — список вех и фильтр «показать карточки вехи».
7. Закрытие окна возвращает на карту; на узле метода остаётся полоска «сколько в работе / сколько готово».

В Hub доска только для чтения: отчёт и фильтры доступны, перетаскивание и новые рёбра — нет.

## Какие сценарии для агента подключаются

| Сценарий (skill) | Роль относительно канбана |
|------------------|---------------------------|
| <code>koi-grill-experiment</code> | До запуска: интервью по постановке → черновик §1–§3 отчёта и карточка в <code>backlog</code> (или уточнение существующей). |
| <code>koi-execute-card</code> | Закон колонок: сразу <code>backlog</code> → <code>running</code>, по ходу галочки в §3 отчёта, в конце <code>running</code> → <code>done</code> до ответа человеку. |
| <code>koi-report-review</code> | Четыре критика по отчёту; та же синхронизация колонок, что у execute. |
| <code>koi-done-research</code> | После <code>done</code>: вопрос/ответ и рассказ в <code>research.json</code> по методу и карточке. |
| <code>koi-card-autoresearch</code> | Долгий прогон одной карточки (роли manager / researcher / debugger); внутри опирается на <code>koi-execute-card</code>. |
| <code>koi-prose-style</code> | Заголовок и описание карточки в интерфейсе — короткий title, детали в <code>desc</code>. |

Руками колонки тоже двигаются; сценарии держат отчёт и колонку согласованными, когда работает агент.

## Как устроено технически

### Хранение в Markdown

В <code>project.md</code> сразу после текста метода:

```markdown
<!-- koi:kanban board-<method-id> -->
| backlog | running | done | successful |
| --- | --- | --- | --- |
| Заголовок <!-- id:c1 desc:… tags:gpu deps:c0 created:… updated:… --> | | |
```

Парсинг: <code>koi/core/md_io.py</code> (<code>KANBAN_START_RE</code>, метаданные карточки в HTML-комментарии). Нормализация колонок: <code>normalize_kanban_board</code>. Модель: <code>ExperimentCard</code>, <code>KanbanBoard</code> в <code>koi/core/models.py</code>; владелец доски — только <code>method</code> (<code>KANBAN_OWNER_TYPES</code>).

Команды API: <code>koi/projects/commands.py</code> (создать карточку, сменить колонку, теги, <code>depends_on</code>). Зависимости: <code>koi/projects/kanban/dependencies.py</code>, раскладка DAG: <code>koi/projects/kanban/layout.py</code>. Отчёты: <code>koi/adapters/card_reports.py</code>.

### Клиент

Модальное окно: <code>#kanban-modal</code> в <code>web/index.html</code>. Логика: <code>openKanbanModal</code>, перетаскивание, фильтры в <code>web/app.js</code>; DAG — <code>web/kanban-dag.js</code>. Под узлом метода на карте — сводка running/done (<code>KANBAN_BELOW_*</code>).

Сохранение снова пишет <code>project.md</code> (и при необходимости файлы отчёта). Синхронизация между машинами — через Git по ветке исследования, не через отдельный протокол канбана.

### Связь с остальным

- Дерево задаёт метод; канбан не создаёт узлов <code>experiment</code> в дереве.
- <code>research.json</code> ссылается на <code>method_id</code> + <code>card_id</code> после разбора «готово».
- Монитор прогона читает артефакты живой карточки (<code>koi/projects/live_artifacts.py</code>, <code>web/card-live.js</code>) — <a href="monitor.html">страница монитора</a>.

## Связанные страницы

- <a href="research-tree.html">Исследовательское дерево</a>
- <a href="index.html">Обзор архитектуры</a>
- <a href="monitor.html">Монитор прогона</a>
- <a href="knowledge.html">База знаний</a>

<p class="callout">Текст: <code>content/kanban.md</code>. Медиа: <code>media/kanban-hero.*</code>.</p>
