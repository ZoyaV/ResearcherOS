---
name: koi-visual-qa
description: >-
  Capture and inspect KOI UI visually. Use when checking mindmap layout,
  method question badges (? N | M), modals, kanban, or any visual regression
  in web/. Requires KOI dev server on 8080.
---

# KOI visual QA

## Prerequisites

```bash
KOI/scripts/koi-serve.sh status   # API 8010 + UI 8080 must be up
```

One-time setup (Python Playwright, works on remote server without npm):

```bash
cd KOI
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/playwright install chromium
```

## Capture screenshots

```bash
KOI/.venv/bin/python KOI/.cursor/skills/koi-visual-qa/scripts/ui_snapshot.py
```

Output: `KOI/.run/ui-screenshots/`

| File | What it shows |
|------|----------------|
| `01-mindmap.png` | Full mindmap |
| `02-method-hover.png` | `? N \| M` badge on hover |
| `03-questions-modal.png` | Выводы modal |
| `04-kanban-modal.png` | Kanban modal |

Read PNG files with the Read tool to inspect visually.

## Cursor built-in browser (desktop)

If Browser MCP tools (`browser_navigate`, `browser_snapshot`) are available:

1. **Settings → Tools & MCP → Browser Automation** → enable, mode **Browser Tab** (not Google Chrome)
2. Toggle off → wait 10s → on; **new Agent chat**
3. Navigate to `http://127.0.0.1:8080/` (or SSH-forwarded URL)

On **SSH remote**, add to Cursor User `settings.json`:

```json
"remote.extensionKind": {
  "anysphere.cursor-browser-automation": ["ui"]
}
```

## What to check for research questions

- Badge `? definite | tentative` appears **only on hover**
- Click badge → **questions modal**, not kanban
- Modal shows **narrative** text, not raw `answer` metrics
- Definite section before tentative section
