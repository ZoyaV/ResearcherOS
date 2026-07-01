# UX checklist

## Objective (agent assigns pass / fail / warning)

### Accessibility

- [ ] Interactive control has accessible name (`aria-label`, visible text, or `<label for>`)
- [ ] `role="dialog"` modals have titled heading (`aria-labelledby`)
- [ ] Decorative icons: `aria-hidden="true"`
- [ ] Focus order logical; no `outline: none` without replacement focus style
- [ ] Status updates use `aria-live` where appropriate (see `#brand-tagline`, `#save-status`)
- [ ] Color not sole indicator — pair with text/icon/shape

### Interaction

- [ ] `type="button"` on buttons that don't submit forms
- [ ] Destructive actions use `.btn-danger` or clear labeling
- [ ] Modal dismiss: backdrop, × button, Escape (if existing pattern extended)
- [ ] Loading/error states don't silently fail (save status, empty lists)

### Layout

- [ ] Works at 1440×900 (default QA viewport) without horizontal scroll (except mindmap pan)
- [ ] `flex-wrap` on toolbars; no fixed widths that clip Russian labels
- [ ] `viewport` meta present (`index.html`)

### Consistency

- [ ] Matches existing modal width modifiers (`--narrow`, `--kanban`, `--report`)
- [ ] Node type colors use existing `.map-node.*` classes
- [ ] Russian UI copy matches informal research-tool tone (no machine-translated stiffness) — **warning only** unless clearly wrong grammar

---

## Subjective (agent MUST NOT pass/fail — only Human review table)

| Topic | Human should judge |
|-------|-------------------|
| **Visual weight** | Do glows/gradients overpower content? |
| **Whitespace** | Comfortable breathing room vs. wasted space |
| **Scannability** | Kanban cards / question lists easy to skim? |
| **Mindmap legibility** | Titles readable at default zoom with 10+ nodes? |
| **Action priority** | Primary CTA draws eye without shouting? |
| **Hover discoverability** | Hidden-until-hover controls (e.g. `?` badge) findable? |
| **Copy quality** | Natural Russian; right level of detail for researchers |
| **Empty states** | Helpful vs. bleak when no data |
| **Delight vs. noise** | Neon aesthetic supports focus, not distraction |
| **Cross-theme polish** | Light mode feels intentional, not an afterthought |

---

## Human review prompts

Copy into the report **What to check** column:

1. **Spacing**: «При взгляде на [экран/компонент] — пропорции и отступы кажутся сбалансированными? Ничего не давит и не “провисает”?»
2. **Hierarchy**: «Сразу понятно, что главное действие на этом экране?»
3. **Density**: «При типичном объёме данных (много узлов/карточек) читается ли интерфейс без усталости?»
4. **Copy**: «Формулировки звучат естественно по-русски для исследователя?»
5. **Aesthetic**: «Кибер/neon стиль KOI здесь уместен или перегружает?»
6. **Theme**: «Светлая тема на скриншоте выглядит так же продуманно, как тёмная?»
7. **Discoverability**: «Пользователь без подсказки найдёт [конкретный контрол]?»
8. **Feel**: «Hover/transition ощущаются отзывчивыми, не дёргаными?»

Add row only when the change touches that concern; don't pad with generic rows.
