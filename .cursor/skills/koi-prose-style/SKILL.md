---
name: koi-prose-style
description: >-
  Review and rewrite KOI user-facing prose (kanban cards, project.md nodes,
  research question/narrative, knowledge docs) for natural-language style.
  Launches a readonly style-reviewer subagent before saving. Use when adding
  or editing cards on a board, descriptions, hypotheses, method titles, or
  any text shown in the KOI UI without extra documentation.
---

# KOI: стиль пользовательского текста

Перед записью в файл любого **человекочитаемого** текста проекта — заголовки
узлов, описания, карточки канбана (`title` и `desc`), `question`/`narrative` в
`research.json`, курируемые `knowledge/*.md` — прогони цикл **черновик →
subagent-ревью → переписать → снова ревью**. В файл пиши только после `PASS`.

Технические поля (`id`, `answer`, пути, fenced json в отчётах) этим скиллом не
покрываются — там действуют форматные ворота из `agent/AGENTS.md`.

## Когда запускать

1. Пользователь просит добавить/изменить карточки на канбане.
2. Правка `koi-structure/project.md` (problem, cause, method, remediation).
3. Формулировка `question` / `narrative` (в т.ч. внутри `koi-done-research`).
4. Курируемые документы в `projects/<id>/knowledge/*.md`.
5. Любой текст, который увидит человек в UI без открытия отчёта или глоссария.

Если задача **только** про вывод по done-карточке — сначала `koi-done-research`,
но проверку стиля для `question`/`narrative` всё равно выполни по workflow ниже.

## Правила стиля (обязательные)

Должно быть максимально на естественном языке, постараться не смешивать несколько языков сразу, если к примеру нужно название метрики на английском сказать, то нужно сначала говорить естественным языком что за метрика, к примеру "количество кликов на рекламу" а потом в скобках абривиатуру, любые надписи в проекте должны быть написаны так, чтобы человек мог понять без дополнительной документации о проекте.

### Дополнительные уточнения (не противоречат правилам выше)

| Область | Писатель | Ревьюер |
|---------|----------|---------|
| Язык интерфейса | Русский для учебных/русскоязычных проектов; один язык на фразу | Смешение EN/RU в одной фразе без пояснения — нарушение |
| Аббревиатуры | Сначала смысл, потом `(CTR)`, `(CPC)`, `(SFT)` и т.д. | Голые `CTR analysis` / `проверить SFT` без расшифровки — нарушение |
| Карточка канбана | Заголовок — что делаем; `desc` — что получится на выходе | Заголовок с жаргоном или id вместо смысла — нарушение |
| `research.json` | `question` + `narrative` — для человека; сырые метрики — в `answer` | Числа и шаги обучения в narrative — нарушение |
| Идентификаторы | `id:fmt-aggregate` в HTML-комментарии — ок; в видимом тексте — нет | Видимый `fmt-aggregate` / `kb-sft` — нарушение |

Эталонные примеры: [examples.md](examples.md) и `bicycle_problem/koi-structure/project.md`.

## Workflow

### 1. Черновик

Собери **только проверяемые фрагменты** — по одному блоку на карточку или поле.
Не смешивай с diff всего файла. Формат для ревьюера:

```text
## Fragment: <карточка id:… | узел cause:… | research question rq-…>
<title или заголовок узла>
desc: <если есть>
---
<остальной видимый текст>
```

### 2. Subagent-ревьюер

Запусти **ровно один** subagent:

- `subagent_type`: `generalPurpose`
- `readonly`: `true`
- `run_in_background`: `false`
- `description`: `KOI prose style review`

Промпт subagent'у (подставь фрагменты и путь к examples):

```text
You are a KOI prose style reviewer. Read-only. Do not edit files.

Style rules (mandatory):
- Должно быть максимально на естественном языке, постараться не смешивать несколько языков сразу, если к примеру нужно название метрики на английском сказать, то нужно сначала говорить естественным языком что за метрика, к примеру "количество кликов на рекламу" а потом в скобках абривиатуру, любые надписи в проекте должны быть написаны так, чтобы человек мог понять без дополнительной документации о проекте.

Also check:
- No bare English jargon without Russian explanation first
- question/narrative: no raw metrics (those belong in answer)
- Visible text must not contain internal ids (fmt-aggregate, kb-sft, …)
- One language per phrase

Fragments to review:
<paste fragments from step 1>

Reference good/bad pairs in ReseachOS/.cursor/skills/koi-prose-style/examples.md if needed.

Output format (strict):
Line 1: exactly PASS or FAIL
If FAIL: markdown table with columns Fragment | Problem | Suggested rewrite
If PASS: one short sentence why it passes.
```

### 3. Цикл переписывания

- `PASS` → переходи к шагу 4.
- `FAIL` → перепиши **только** указанные фрагменты по колонке Suggested rewrite;
  снова шаг 2. Максимум **3** итерации ревью.
- После 3-го `FAIL` — покажи пользователю таблицу замечаний и спроси, сохранять
  ли как есть или править вручную. **Не пиши в файл** без явного согласия.

### 4. Сохранение

Только после `PASS` — `Write`/`StrReplace` в целевой файл. В ответе пользователю
кратко: «стиль проверен (koi-prose-style), N итераций» или перечисли что изменил
ревьюер.

## Быстрая самопроверка (если subagent недоступен)

Прочитай каждый фрагмент вслух. Если без знания проекта неясно, о чём речь —
перепиши. Аббревиатуру без пояснения — добавь расшифровку в скобках. Это
запасной путь; при доступном Task/subagent предпочитай полный цикл выше.

## Связанные скиллы

- `koi-report-review` — отчёты §1–§N: четыре критика (стиль, постановка, SMART, результаты)
- `koi-done-research` — вывод по done-карточке; narrative/question проверяй здесь
- `koi-knowledge-curator` — курируемые knowledge-документы; перед сохранением — здесь
- `koi-project-sync` — commit после правок `koi-structure/`
