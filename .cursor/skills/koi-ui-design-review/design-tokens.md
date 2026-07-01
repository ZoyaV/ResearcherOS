# KOI design tokens & components

Source of truth: `web/styles.css`, `web/index.html`.

## Themes

- `data-theme="dark"` (default) and `data-theme="light"` on `<html>`
- Persisted: `localStorage.koi-theme`
- Every new surface/border/shadow must look correct in **both** themes

## Color tokens (use via `var(--name)`)

| Token | Role |
|-------|------|
| `--bg`, `--bg-elevated` | Page / raised surfaces |
| `--glass`, `--border` | Glass panels, dividers |
| `--text`, `--muted` | Primary / secondary text |
| `--pink`, `--purple`, `--cyan`, `--orange`, `--lime`, `--peach` | Accent palette |
| `--grad-hero`, `--grad-warm`, `--grad-cool`, `--grad-lime` | Gradients (buttons, logo) |
| `--glow-pink`, `--glow-cyan`, `--glow-purple` | Neon glow (dark); subtle shadow (light) |
| `--surface-topbar`, `--surface-modal`, `--surface-board`, `--surface-col` | Layout surfaces |
| `--surface-card`, `--surface-card-hover`, `--surface-input` | Cards, inputs |
| `--surface-muted-btn`, `--surface-muted-btn-hover` | Secondary buttons |
| `--backdrop` | Modal overlay |
| `--btn-primary-text`, `--btn-fill`, `--btn-fill-hover`, `--btn-border` | Buttons |
| `--select-border`, `--select-glow` | Select controls |
| `--link`, `--code-bg`, `--pre-bg` | Markdown / code |
| `--kanban-stats`, `--shadow-heavy`, `--shadow-modal-accent` | Kanban, depth |

Hex literals belong **only** in `:root` / `[data-theme]` token definitions — not in component rules.

## Typography

| Use | Font |
|-----|------|
| Body, UI | `"Outfit", system-ui, sans-serif` |
| Logo, strong display | `"Syne", sans-serif` |

Sizes: toolbar `0.78–0.8rem`, tagline `0.75rem`, logo `1.85rem`. Line-height body `1.45`.

## Spacing & radius

- Button/input radius: `10px`
- Modal panel radius: `16px` (see `.modal-panel`)
- Toolbar/topbar gap: `0.5–0.75rem`
- Mindmap node padding: see `.map-node` (don't invent new node chrome)

## Component patterns (reuse)

### Buttons

```html
<button type="button" class="btn">Secondary</button>
<button type="button" class="btn btn-primary">Primary</button>
<button type="button" class="btn btn-danger">Destructive</button>
<button type="button" class="btn btn-small">Compact</button>
```

Icon-only: add `aria-label`, keep min ~44px hit area (see `.btn-theme`).

### Modal shell

```html
<div id="…" class="modal hidden" role="dialog" aria-labelledby="…">
  <div class="modal-backdrop" data-close="…"></div>
  <div class="modal-panel"><!-- or --narrow, --kanban, --report -->
    <button type="button" class="modal-close" data-close="…" aria-label="Закрыть">×</button>
    …
  </div>
</div>
```

Open: remove `hidden` from modal, add `body.modal-open`.

### Mindmap nodes

- Wrapper: `.node-wrap` (+ modifiers: `.has-kanban-wrap`, `.has-research-questions`)
- Node: `.map-node` + type class: `.problem`, `.cause`, `.cause_evidence`, `.remediation`, `.method`, `.experiment`
- Add node: `.map-node.add-node`

### Kanban

- Modal: `.modal-panel--kanban`
- Cards: existing kanban card markup in `app.js` — match drag handle, expand, column chrome

### Forms

- `.form`, `.form-actions`, `.form-actions--split`
- `.inline-edit-text` / `.inline-edit-field` for in-modal editing
- Hidden labels: `.sr-only`

### Markdown in modals

- `.modal-panel--report`, `.markdown-preview` — use existing md-* classes

## Background effects

- Mesh gradients: `body::before` (theme-specific)
- Grid: `body::after` with `--grid-line`
- Don't add competing full-page backgrounds behind modals

## Motion

- Default transition: `0.15s` (buttons), `0.45s` (tagline fade)
- Hover lift: `translateY(-1px)` on `.btn:hover`
- New animations: check both themes; avoid layout thrashing on mindmap
