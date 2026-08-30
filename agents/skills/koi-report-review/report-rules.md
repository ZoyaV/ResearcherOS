# Report writing rules

A concise reference for people and language models. Structure and inline guidance
are in [report-skeleton.md](report-skeleton.md). If formatting rules conflict
(bold, headings, and similar choices), this file takes priority.

Write reports so that **Sections 1, 2, N.2 (conclusions), and prose in N.1
(results)** can move into a paper with minimal editing. Local paths and slugs
belong in Section 3 (setup and collection), not Section 4+.

## Section structure

| Section | Content |
|---------|---------|
| Sections 1–2 | Rationale and metric |
| Section 3 | Setup for each run, **Tasks** (`- [ ]`), collection, commands, done criterion |
| Sections 4, 5, … | Execution only: result tables and conclusions |
| Appendix | Raw dumps and complete paths |

Do not repeat Section 3 setup and collection in Section 4+; “see Section 3.1” is
enough.

---

## Tasks (SMART and concise)

Every task must be understandable **without repository context**. Start with a
plain action and public names; put technical details at the end in
`(local: …)`.

One- or two-line formula: **action** + **data/model (public name)** +
**measurable output or destination** + `(local: script, flag, file)`.

| Letter | Requirement |
|--------|-------------|
| **S** | Use a concrete verb: “generate,” “calculate,” “fill Table A,” not “run a sweep” or “do the experiment” |
| **M** | State an explicit completion criterion: “JSON with \|distinct\| for five prompts,” “Table C: base vs adapter” |
| **A** | Bound the run (five prompts, four N values), not the whole kanban card |
| **R** | Link to Section 1/2 in one phrase when relevance is not obvious |
| **T** | State ordering: “after Section 3.1,” “before closing the card” |

Names in tasks:

- Use “base Qwen3-4B-Instruct” and “adapter after mini-SFT,” not unexplained
  `MODEL=base` or `step50`.
- Use “stalled-transition sample” and “held-out CrafText test,” not only a slug
  or id in the main text.

Examples:

- Good: `[ ] On the stalled-transition sample (five prompts), generate
  5/64/128/256 responses per prompt with the base model, count unique actions,
  and save numeric JSON (local: MODEL=base, sweep_base_….json)`
- Good: `[x] In Section 5.2, answer whether increasing N expands the action set;
  compare the adapter and base model using Table C`
- Bad: `[ ] Run sweep on NavCraft-stuck-5`, `[ ] MODEL=base`,
  `[ ] Improve diversity`

Use `- [x]` only after satisfying the M criterion.

---

## Paper-facing names (datasets, environments, and samples)

In Section 3, assign every dataset, test sample, environment, and major artifact
a short, stable **public name** suitable for paper prose. Use one name per entity
throughout a report.

| Location | Naming rule |
|----------|-------------|
| Sections 1 and 2 prose, Section N.2 conclusions, `Protocol:` line | Public name plus one clarification when needed |
| Section 3 setup, collection, and tasks | Public name in the main text; `path.json` and flags under `local:` |
| Headings `##`–`####` | Meaning and scale, never file slugs |

If the user supplied no name, propose a meaningful one such as NavCraft-fails or
CrafText-nav-test and record it in Section 3. Ask when uncertain.

Examples:

- Good conclusion: “On the held-out CrafText navigation test, mean diversity
  increased from 1.50 to 1.78.”
- Bad: “On `dif_action_test_matched_50.json`, the mean increased…”
- Section 3: `NavCraft-fails — …; local data/….json, 3,348 items.`

In paper prose use “base Qwen3-4B-Instruct” or “adapter after 50 LoRA steps.”
Keep `global_step_50` in Section 3 or the artifact list.

---

## Do

- Write in the team's voice: “we train,” “we recorded.”
- In Section 1, state the problem, action, and success criterion without local filenames.
- Make the goal measurable; avoid bare “improve” or “optimize.”
- For **every** run in Section 3.x, include Summary, data/model/script fields, a
  Tasks checklist, `#### Data collection`, and bash when needed.
- Tasks are SMART steps (run → artifact → Section N.1 → Section N.2), not
  conclusions or copies of tables.
- Section 4+ contains only `### N.1 Results` and `### N.2 Conclusions`, with a
  link to the corresponding Section 3.x.
- Use public sample and environment names in Section 2 and conclusions.
- Write meaningful `##` / `###` / `####` headings without slugs or
  `(N=5, matched-…)`.
- Put protocol parameters in Section 2 and the `Protocol:` line under a table,
  not in the table title.
- Section 3.x Data collection covers training volume and preparation;
  Section N.1 contains checkpoint tables; Section N.2 contains insights.
- Make the first table in Section N.1 the final Section 2 protocol. Put
  diagnostics separately and label them “not the final test.”
- In conclusions, write “Table A/B/C shows …” plus an overall conclusion;
  state the judgment first and numbers second.
- Keep the report header Status synchronized with kanban.

---

## Do not

- Do not use `**bold**` for emphasis.
- Do not repeat Section 3 setup and collection in Section 4+ (data lists, bash,
  or “no collection”).
- Do not mention local filenames in Section 1, Section 2 prose, conclusions, or
  `Protocol:` lines.
- Do not place `.json`, `.sh`, or run ids in `##`–`####` headings.
- Do not write conclusions below tables in Section N.1; use Section N.2.
- Do not put goals in Section N.1 or results in Section 1.
- Do not declare done based on diagnostics when Section 3 requires the Section 2 final test.
- Do not paste raw logs into Section N.1 instead of aggregates.
- Do not use unexplained jargon in Tasks (`sweep`, `MODEL=base`, a dataset slug
  as its only name) or vague verbs such as “refine” and “improve” without an
  object and completion criterion.

---

## Checklist before saving

- [ ] The report body contains no `**`.
- [ ] Public names are defined in Section 3; Sections 1, 2 prose, and conclusions contain no file slugs.
- [ ] Every Section 3.x has concise SMART Tasks; Section 4+ contains only results and conclusions.
- [ ] Section N.1 has no conclusions; interpretation is in Section N.2.

---

## Reference examples

The canonical structure is Section 3 (setup, SMART tasks, collection) followed by
Section 4+ (results and conclusions). Example report names:

- `.../Test_action_space_expansion_as_sampling_increases.md`
- `.../Run_SFT_training_on_the_dataset.md`
- `.../Fine_tune_the_SFT_checkpoint_with_reinforcement_learning.md`
