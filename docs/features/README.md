# Features docs (`docs/features`)

Отдельный набор страниц про устройство ResearcherOS: архитектура и локальные фичи.

Стиль — как у ResearcherOS (Outfit / Syne, те же токены). CSS самодостаточный в `css/features.css`. Пока не вшито в продукт: правите файлы здесь, смотрите локально.

## Локально

```bash
cd ReseachOS/docs/features
python3 -m http.server 8766
# http://127.0.0.1:8766/
```

## Структура

| Путь | Назначение |
|------|------------|
| `index.html` + `content/overview.md` | Главная (архитектура) |
| `research-tree.html` + `content/research-tree.md` | Исследовательское дерево |
| `kanban.html` + `content/kanban.md` | Канбан экспериментов |
| `monitor.html` + `content/monitor.md` | Монитор прогона |
| `knowledge.html` + `content/knowledge.md` | База знаний |
| `chat.html` + `content/chat.md` | Research Chat |
| `related-work.html` + `content/related-work.md` | Related Work |
| `paper.html` + `content/paper.md` | PaperDraft |
| `widgets.html` + `content/widgets.md` | Виджеты |
| `full_schema.html` | Интерактивная схема архитектуры |
| `media/` | Картинки и видео (вставляете сами) |
| `css/`, `js/` | Общий каркас раздела |

## Состав

1. **Главная (overview)** — три слоя: Research Project · Local · Hub + схема
2. **Каталог локальных фич** — восемь страниц (дерево … виджеты)
3. **Шаблон страницы фичи** — медиа → как работает → UI → сценарии агента → техника

Контент — Markdown в `content/`. Медиа — в `media/`.
