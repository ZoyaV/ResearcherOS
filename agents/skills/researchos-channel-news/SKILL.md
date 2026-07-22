---
name: researchos-channel-news
description: >-
  Prepare ResearchOS product development news for README.md and the Telegram
  channel @researcher_os in parallel: draft README News row, channel caption,
  prose-critic pass, UI screenshot, show the user the full post, and publish
  only after explicit OK. Use when updating README News, shipping a product
  feature, or posting development news to the ResearcherOS channel — never for
  experiment metrics.
---

# ResearchOS channel news

Новости **разработки продукта** ResearchOS: строка в `README.md` § News **и**
пост в Telegram-канал `@researcher_os`. Не эксперименты, не метрики прогонов.

Секреты: `researcheros_bot/.env` (`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`).
Публикация: `researcheros_bot/publish.py` — **только** после явного OK пользователя.

## Когда запускать

1. Пользователь просит обновить News / README / «новости разработки».
2. Закрыли заметный product-фичу (UI, Hub, sync, layout, CLI) и нужно анонсировать.
3. Хук напомнил после правки `README.md`.

Не запускать для: результатов экспериментов, paper drafts, kanban-карточек исследований.

## Жёсткие правила

1. **Два артефакта вместе:** строка README News (EN, как в таблице) + Telegram-пост (RU по умолчанию).
2. **Критик прозы обязателен** до показа пользователю (цикл ниже). Без `PASS` — не показывать как готовый пост.
3. **Картинка обязательна:** скрин релевантной области UI (не логотип, не абстрактный градиент).
4. **Показ → OK → publish.** Пока пользователь не сказал `ок` / `ok` / `выложи` / `publish` — **не** вызывать `publish.py --send`.
5. Хук **не** публикует. Скрипт без `--send` — только dry-run.

## Workflow

### 1. Суть изменения

Одной фразой: что изменилось для пользователя продукта (не внутренний id/путь).

### 2. Черновик README News

Добавь/обнови верхнюю строку в `ReseachOS/README.md` § `## News`:

```markdown
| YYYY-MM-DD | **Короткий title** — 1–2 предложения: что shipped и зачем. Ссылка на ADR/docs если есть. |
```

Стиль как у соседних строк: English, жирный короткий title, без внутренних card id.

### 3. Черновик Telegram-поста

Создай каталог:

```text
researcheros_bot/drafts/YYYY-MM-DD-<slug>/
  caption.md    # текст поста
  image.png     # скрин (шаг 5)
```

Формат `caption.md` (HTML, Telegram `parse_mode=HTML`):

```text
<b>Заголовок без жаргона</b>

1–3 коротких абзаца: что появилось и кому полезно.
Без метрик экспериментов. Без внутренних id (fmt-…, kb-…).
По желанию одна ссылка (GitHub / docs).
```

Лимиты: лучше ≤1024 символов (тогда текст уйдёт caption'ом к фото). Абсолютный потолок сообщения — 4096.

### 4. Критик прозы (обязательно)

Запусти **ровно один** readonly subagent (`generalPurpose`, `readonly: true`,
`run_in_background: false`, description: `channel news prose review`).

Промпт:

```text
You are a ResearchOS channel-news prose reviewer. Read-only. Do not edit files.

Audience: Telegram channel @researcher_os — product development news for ResearchOS users.
Language: Russian by default (unless the draft is explicitly English).
Rules:
- Natural language; explain any English term before the acronym
- No experiment metrics, no paper claims, no kanban/research jargon without plain explanation
- No internal ids (fmt-aggregate, board ids, file paths as the main point)
- Short: scannable on mobile; no marketing spam / emoji walls
- Title must be understandable without knowing the codebase

Fragments:
## Fragment: README News row
<paste English README cell>

## Fragment: Telegram caption
<paste caption.md>

Output format (strict):
Line 1: exactly PASS or FAIL
If FAIL: markdown table Fragment | Problem | Suggested rewrite
If PASS: one short sentence why it passes.
```

Цикл: `FAIL` → перепиши → снова ревью. Макс **3** итерации. После 3-го `FAIL` —
покажи таблицу пользователю и спроси, как править. **Не** считай пост готовым без `PASS`
или явного «оставь как есть».

### 5. Скрин UI

Покажи **ту область интерфейса**, которую анонсируешь.

Предпочтительно:

```bash
# UI должен быть поднят: ./scripts/koi-serve.sh status
ReseachOS/.venv/bin/python ReseachOS/.cursor/skills/koi-visual-qa/scripts/ui_snapshot.py
```

Скопируй лучший кадр в `drafts/…/image.png`, либо сделай целевой screenshot через
Playwright/browser на нужный экран (модалка, DAG, Hub, sidebar, …).

Проверь PNG через Read: если скрин пустой/не тот экран — пересними. Без картинки пост не готов.

### 6. Показ пользователю (гейт)

В ответе покажи:

1. Строку README News (как будет в таблице).
2. Полный текст `caption.md`.
3. Картинку (путь + встроенный preview через Read).
4. Результат критика (`PASS`, N итераций).
5. Dry-run:

```bash
python researcheros_bot/publish.py --draft drafts/YYYY-MM-DD-<slug>
```

Спроси явно: «Выкладываем в @researcher_os?»

### 7. Публикация

Только после `ок` / `ok` / `выложи` / `publish`:

```bash
python researcheros_bot/publish.py --draft drafts/YYYY-MM-DD-<slug> --send
```

Сообщи message_id / ok. README News можно закоммитить отдельно по просьбе пользователя
(коммит сам не делай, пока не попросили).

## Связанные скиллы

- `koi-prose-style` — стиль UI/kanban; для канала используй критика из §4 (другие правила длины).
- `koi-visual-qa` — снимки UI.
- Не путать с experiment/report skills.

## Чеклист

- [ ] README News row готов
- [ ] `caption.md` + `image.png` в `researcheros_bot/drafts/…`
- [ ] prose critic `PASS` (или явное согласие после FAIL)
- [ ] пользователь увидел пост и картинку
- [ ] `--send` только после OK
