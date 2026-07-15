---
name: koi-ui-design-review
description: >-
  Reviews KOI web/ UI edits for design-system compliance, a11y, and UX
  heuristics. Runs static lint, visual capture, and auto-fixable checks; returns
  a human-review list for subjective items. Use when editing web/, styles.css,
  app.js, index.html, UI components, modals, kanban, mindmap, buttons, or
  themes.
---

# KOI UI design review

Run **after** UI edits in `web/` (or before finishing the task). Pair with [koi-visual-qa](../koi-visual-qa/SKILL.md) for regression screenshots.

## Prerequisites

```bash
KOI/scripts/koi-serve.sh status   # API 8010 + UI 8080 for visual pass
```

## Workflow

Copy checklist and track progress:

```
Review progress:
- [ ] 1. Read design-tokens.md (if new styles/components)
- [ ] 2. Run static lint on changed files
- [ ] 3. Fix all Blocking auto findings
- [ ] 4. Visual capture of affected screen(s)
- [ ] 5. Run objective checklist (both themes)
- [ ] 6. Emit report (template below) — include Human review section
```

### 1. Before editing

Read [design-tokens.md](design-tokens.md). Reuse existing classes (`.btn`, `.modal`, `.map-node`, …) before adding new ones.

### 2. Static lint

On changed files under `web/` (checks **git diff added lines** only):

```bash
KOI/.cursor/skills/koi-ui-design-review/scripts/lint-ui-css.sh web/styles.css web/app.js
```

Full-file scan (rare): append `--all`. Fix every **blocking** lint hit before reporting done.

### 3. Visual capture

Navigate to the affected UI state. Prefer:

```bash
KOI/.venv/bin/python KOI/.cursor/skills/koi-visual-qa/scripts/ui_snapshot.py
```

Or Browser MCP → `http://127.0.0.1:8080/`, interact to reach changed UI, `browser_take_screenshot`.

Capture **dark and light** theme if styles changed (`btn-theme` or `localStorage koi-theme`).

### 4. Objective checks (agent decides pass/fail)

| Check | Pass criteria |
|-------|---------------|
| Tokens | Colors/surfaces use `var(--*)`, not raw hex in rules |
| Themes | New surfaces work in `[data-theme="dark"]` and `[data-theme="light"]` |
| Typography | Body `Outfit`, display/logo `Syne` — no new font families |
| Buttons | `.btn` / `.btn-primary` / `.btn-danger`; `type="button"` on non-submit |
| Modals | `.modal` + `.modal-backdrop` + `.modal-panel`; `role="dialog"`; close with `aria-label` |
| Forms | `<label>` or `.sr-only` + `for=`; native inputs styled via existing patterns |
| Icons | Decorative SVG → `aria-hidden="true"`; icon-only buttons → `aria-label` |
| Motion | Transitions ≤ 0.45s; respect `prefers-reduced-motion` if adding animation |
| Touch | Click targets ≥ 44×44px for primary actions (padding or hit area) |

Full heuristics: [ux-checklist.md](ux-checklist.md) — only **objective** rows get pass/fail from the agent.

### 5. Subjective → Human review only

**Never** mark these as auto-pass or auto-fail. Always list them under **Human review** with location + what to look at:

- Visual balance, spacing rhythm, “does it feel crowded?”
- Copy: tone, clarity, Russian wording, label length on mindmap nodes
- Information hierarchy: is the primary action obvious?
- Color harmony beyond token presence (gradient weight, glow intensity)
- Mindmap density / kanban card scannability at realistic data volume
- Micro-interactions: hover affordance “feel”, animation easing taste
- First-time user comprehension (canvas hint sufficient?)
- Brand fit: cyber/neon aesthetic vs. readable research tool

Use the prompt templates in [ux-checklist.md](ux-checklist.md) § Human review prompts.

### 6. Report template

Always end UI work with this structure:

```markdown
## UI design review

### Auto — fixed
- [what was wrong → what you changed]

### Auto — passed
- [objective checks that passed]

### Auto — warnings (non-blocking)
- [lint suggestions, minor a11y gaps]

### Human review
| # | Where | What to check | Why agent can't decide |
|---|-------|---------------|------------------------|
| 1 | `web/...` / screenshot `...` | … | … |

### Screenshots
- dark: `path or description`
- light: `path or description` (if applicable)
```

If there are **no** subjective concerns, still include:

```markdown
### Human review
Нет субъективных замечаний — быстрый взгляд на скриншот(ы) выше достаточен.
```

## Integration

- **During implementation**: follow design-tokens; don't wait until the end to lint.
- **After implementation**: full workflow + report before marking task complete.
- **Regression**: if layout-critical, also run koi-visual-qa snapshots.

## Do not

- Approve subjective aesthetics as "LGTM" without Human review section
- Introduce new CSS frameworks or icon packs
- Hardcode colors in component rules (tokens only)
- Skip light theme when touching surfaces, borders, or shadows
