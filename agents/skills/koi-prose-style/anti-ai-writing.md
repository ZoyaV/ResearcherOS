# Anti-AI prose for KOI

This adapts Wikipedia’s “Signs of AI writing”
for short ResearchOS text: nodes, cards, questions, conclusions, and knowledge
documents. These signs are **probabilistic**: one incidental phrase is weak
evidence, while a cluster in one fragment is `FAIL`.

Repair prose with **specific meaning**, not by replacing one AI-sounding word
with another.

For paper writing, see the full A–H checklist at
`.cursor/skills/paper-orchestra-shared/writing_quality_check.md`.

---

## 1. Empty prestige vocabulary

Avoid clusters of:

| Avoid | Prefer |
|-------|--------|
| revolutionary, cutting-edge, groundbreaking | state exactly what changed |
| comprehensive, nuanced, multifaceted | give one concrete qualification |
| pivotal, crucial, critical without evidence | explain why using a fact |
| seamless, synergy, holistic | describe the actual connection |
| landscape, tapestry, delve, underscore, foster | remove and start with content |
| “this highlights the importance of …” | give the consequence or measurement |

Other common markers: in today's world, it is no secret, it is worth noting,
plays a key role, opens new horizons.

**Repair:** delete the phrase and retain the factual claim.

---

## 2. Throat-clearing and stock conclusions

Do not begin with “It is worth noting that,” “It is important to understand,”
“In the context of,” or “In an era of.”

Do not end a paragraph or description with “Overall,” “In summary,” “Thus one
can conclude,” or “despite challenges, it continues to evolve” unless a new
fact follows.

**Repair:** begin with the point and remove endings that add no information.

---

## 3. Rhetoric instead of meaning

| Pattern | Problem | Better |
|---------|---------|--------|
| not only X but also Y | often empty symmetry | state X and Y directly |
| not X but Y without a likely misconception | theatrical contrast | use one direct statement |
| always exactly A, B, and C | forced rule of three | use the number the content requires |
| from toy tasks to real systems | false range | name the actual cases |

---

## 4. Promotional significance

Avoid press-release language such as rich, unique contribution, marks a shift,
serves as a testament, and trailing “highlighting,” “ensuring,” or
“underscoring” clauses without a measurable consequence.

**Repair:** say who benefits, by how much, and under which conditions, or remove it.

---

## 5. Vague attribution

Do not write “researchers believe,” “experts note,” “it is widely known,” or
“many studies show” without naming or linking the source.

**Repair:** cite the source or remove the attribution.

---

## 6. Punctuation and presentation

- Break up clusters of em dashes with sentences or parentheses.
- Avoid unnecessary Title Case in node and card labels.
- Remove decorative bold and emoji from UI text.
- Visible placeholders such as `TODO`, `lorem`, `insert here`, or “to be added
  later” are `FAIL`.

These issues usually appear in `desc` and knowledge prose rather than short
titles.

---

## 7. Plain verbs

Prefer “is” and “has” over ornate alternatives such as serves as, stands as,
boasts, features, or offers when they merely mean existence or possession.

---

## Reviewer order

1. Empty words, significance claims, and throat-clearing
2. Rhetorical patterns and vague experts
3. Em dashes, placeholders, and promotional tone

Always also check: natural English, one language per phrase, explained
abbreviations, titles at most eight words, and no visible internal ids.
