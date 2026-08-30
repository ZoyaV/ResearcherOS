---
name: koi-project-onboard
description: >-
  Attach an existing code repository to ResearchOS through a persistent Socratic
  interview with semantic quality gates (problem → program → cause/hypothesis →
  method), then a cold-reader title-only clarity loop (at most six iterations),
  koi-prose-style, writing tree/REPO/koi-structure/project.md, and install_cli
  (orphan koi/research + tree worktree). Trigger when the user asks to connect,
  onboard, or attach a repository, or points to a sibling code folder without
  koi-structure/.
---

# KOI: attach and onboard a project

Attach a repository with **existing code** to ResearchOS and build a research
skeleton:

```text
problem → cause → remediation|cause_evidence → method
```

This follows ADR-001. Canonical storage:

```text
tree/<repo>/koi-structure/project.md   # koi/research worktree
<repo>/                                # code, any branch
```

This is not empty-project creation and not a full Related Work review. For a
new project without code, use
`python -m koi.projects.install_cli install <name> --create`.

Node type checks and interview frames are in
[framing-checks.md](framing-checks.md).

## Mandatory framing brief

Maintain and eventually write
`tree/<repo>/koi-structure/onboard-brief.md` (legacy:
`<repo>/koi-structure/...`) using
[onboard-brief.template.md](onboard-brief.template.md). It records the high-level
goal/problem/cause/hypothesis/method agreed in layers 3A–3C.

Before **any** node/card title edit — layer fixation, clarity loop, prose pass,
or later tree edit — reread `onboard-brief.md` and compare every title to it.
The cold reader must not receive this file.

## Mandatory prose discipline

Every user-facing onboarding message — brief, literature comparison, question,
comment, fixed node, or skeleton summary — follows
[`koi-prose-style`](../koi-prose-style/SKILL.md). Run a prose self-check before
every message. When fixing a layer and before writing `project.md`, run the full
read-only subagent cycle until `PASS`. Never write without PASS.

The dialogue is Socratic, academic, and layered. Do not dump complete Frame
A/B/C alternatives. Move from problem to cause/hypothesis to method, asking
several questions per layer. Continuously triangulate literature, researcher
answers, and code using natural academic English, not agent metadata such as
gap, claim, KOI node, category error, or raw module/status labels.

## When to run

1. The user asks to connect/onboard/attach `<path>` to ResearchOS.
2. A sibling or scanned repository contains code but lacks
   `tree/<repo>/koi-structure/project.md` and legacy
   `<repo>/koi-structure/project.md`.
3. The researcher needs help formulating a high-level problem or cause.

Do not run when:

- a tree exists and the user needs a card: use **koi-grill-experiment**;
- a full Introduction/Related Work/BibTeX review is needed: use the literature
  review agent or paper pipeline;
- only layout/branch sync is needed: use `install_cli install <repo>`;
- only sync for an attached project is needed: use **koi-project-sync**.

## Mandatory pipeline

```text
0 Preflight + scan adjacent programs
→ 1 Code scan
→ 2 Lightweight literature framing
→ 3A Socratic PROBLEM (at least 4 questions) → prose fixation
→ 3PROG Socratic PROGRAM (1–2 questions) → fix programs:
→ 3B Socratic CAUSE+HYPOTHESIS (at least 4 questions) → prose fixation
→ 3C Socratic METHOD (at least 3 questions, seed cards) → prose fixation
→ 5 Cold-reader clarity loop on titles only (at most 6) → best title set
→ 6a Final prose pass
→ 6b Write tree/<repo>/koi-structure/ only after “write”
→ 6c install_cli + sync push for git repositories
→ handoff
```

Do not write `koi-structure/` before layers 3A → 3PROG → 3B → 3C pass, the
clarity loop is complete, and the user says to write. Do not jump from problem
directly to method. After writing a git repository, Section 6c is mandatory.

## 0. Preflight

1. Resolve the **code repository** path, absolute or workspace-relative. It must
   exist. Its folder name becomes `<repo>` under `tree/`.
2. Ensure the repository is a sibling of the engine or under `KOI_SCAN_ROOTS`.
   Warn when it is outside discovery roots because the UI may not see it.
3. If canonical or legacy `project.md` already exists, **do not overwrite**.
   Offer to stop, show the skeleton, make targeted additions in a separate
   session, or run `install_cli migrate` when only layout is legacy. Stop by default.
4. Scan adjacent `tree/*/koi-structure/project.md` and legacy
   `*/koi-structure/project.md` for programs. Build internal
   `existing_programs[]` with program ids/titles and member projects. Do not ask
   about programs until the problem layer is fixed.

## 1. Code scan (no questions)

Do three passes; never ask what files already answer.

| Pass | Inspect | Extract |
|------|---------|---------|
| **Intent** | README, abstracts, paper drafts, top-level directories | Candidate phenomenon/problem |
| **Stakes** | reward/loss, environment wrappers, ablation flags, curriculum | Candidate remediation/method |
| **Evidence** | examples, job directories, train/eval scripts, log hints | Backlog seed cards |

Prepare an internal 5–10 bullet draft: repository purpose, current intervention
bets, evaluation paths, and explicit gaps between stated goals and existing jobs.

Do not name the problem after a feature/method such as diversity bonus or LoRA PPO.

## 2. Lightweight literature framing

The goal is to frame the **phenomenon and mechanisms**, not write Related Work.
Do not invoke a full bibliography/Introduction pipeline.

1. Derive 4–6 searches from the code scan:
   - 2–3 for the phenomenon/failure mode/gap;
   - 2–3 for proposed mechanisms/causes;
   - optionally 1–2 surveys or position papers.
2. Use web search or Semantic Scholar when available.
3. Retain 5–12 relevant papers. For each, record title/year, how it defines the
   problem, proposed cause, and intervention when present.
4. Maintain an internal bank, not a menu shown to the user:
   - 2–3 problem candidates from literature + code;
   - 2–4 causes and linked hypotheses;
   - 1–3 methods from existing jobs;
   - internal labels `code+lit`, `code-only`, `lit-only`.

Use [framing-checks.md](framing-checks.md) for grounding and type gates.

## 3. Socratic academic dialogue

Jointly formulate problem, causes, hypotheses, and methods in field terms,
grounded in literature, code, and the researcher's position. This is a research
interview, not therapy or coaching.

Avoid “what hurts,” emotional priorities, or “explain without modules” as the
only focus. Ask about field contribution, prior work, mechanism, falsification,
and evaluation.

### Prose on every turn

Before sending any message:

1. Draft the turn.
2. Self-check against koi-prose-style and the dialogue prose rules in
   framing-checks:
   - natural English;
   - explain unfamiliar terminology before abbreviation;
   - paper titles may stay verbatim, but explain their framing plainly;
   - no raw pipeline jargon as the opening language;
   - comparisons read as reasoning, not a field log.
3. Rewrite before sending when it fails.
4. At layer fixation and before file writes, run full koi-prose-style to PASS.
5. Keep technical internal notes out of chat.

### Triangulation on every turn

After the user's first answer, connect three sources in prose:

1. one to three papers (authors/year and how they frame the problem/cause);
2. a plain academic paraphrase of the user's position;
3. what the repository measures or changes, without leading with flag names.

For example: “You describe … . This resembles Title (Year), where … . It differs
from Author et al. (Year) because … . In the repository, this distinction appears
in … . This suggests framing the problem as … .” Then ask one question.

Do not use labels such as `Cross-check:` or `Comment:`; write connected prose.

### Turn rules

1. Ask **one question per message**.
2. Minimum question counts are lower bounds, not completion quotas. Close a
   layer only when readiness gates in framing-checks pass.
3. Precede the question with literature/code context in plain prose.
4. Ask for the research position: similarity to prior work, why it matters,
   contribution, mechanism, and evaluation.
5. Classify what the researcher actually said: phenomenon, mechanism, expected
   observation, intervention, protocol, or completed result. Do not trust their
   proposed node label automatically.
6. When an answer is vague, mixed, or incomplete, do not advance. Name one main
   defect and ask one precise question about the missing component.
7. The researcher owns domain meaning; the agent owns classification,
   testability, and wording. Do not ask “is this cause or remediation?” Ask a
   scientific question and classify it yourself.
8. Each next turn begins with prose triangulation and one question.
9. Wait for the answer; do not generate the next question in the same message.
10. At layer end, propose a title and description, state remaining uncertainty,
    and request confirmation of meaning rather than KOI terminology. Fix only on PASS.
11. Push back academically and concretely: identify the failed criterion, explain
    why it breaks the branch, offer 1–3 plausible interpretations, and ask one
    distinguishing question.
12. Never invent a missing domain fact. Label an agent proposal and request correction.

Internal cycle after each substantive answer:

```text
classify substance
→ check node completeness
→ check type
→ check parent linkage
→ choose one main defect
→ concise academic pushback
→ one clarifying question
→ repeat until PASS
```

A short answer is not itself wrong. “Poor generalization” names a topic but not
a complete problem; ask for the object, conditions, observed gap, and expected state.

### 3A. PROBLEM layer

First send a prose brief without questions: 3–5 repository findings and 2–4
papers describing nearby observable problems, without causes or methods.

Then ask at least four questions, one per message:

| Goal | Example |
|------|---------|
| Prior-work comparison | Related work frames the problem as A or B. Is yours similar or different? |
| Observable phenomenon | Which system/object fails, under which conditions, and how does actual behavior differ from expected behavior? |
| Significance | Which field gap or practical decision depends on resolving it? |
| Scope | What tempting neighboring issue should not become the root problem? |

Stop only when one problem passes all readiness gates. Run prose review to PASS,
confirm title/description, and add it to the brief.

### 3PROG. PROGRAM layer

After fixing the problem, show relevant existing programs discovered in preflight
and ask one question: does the project belong to one, stand alone, or need a new
program? For a new program ask a second question to fix a field-level title, not
a method name. Program titles use at most eight words.

Fix `programs:` or explicit “no program” and update the brief.

### 3B. CAUSE + HYPOTHESIS layer

Use the problem as the parent and ask at least four questions:

| Goal | Example |
|------|---------|
| Mechanism | Which single mechanism could produce the observed problem? |
| Parent link | How does that mechanism lead specifically to the problem? |
| Falsification | Which observation would make you abandon this cause? |
| Testable child | Should we test a predicted observation (`cause_evidence`) or an intervention (`remediation`), and what outcome is expected? |

Keep asking until 1–2 causes and 1–2 linked hypotheses pass type/readiness gates.
Run prose review, confirm, and update the brief.

### 3C. METHOD layer

For each hypothesis ask at least three questions:

| Goal | Example |
|------|---------|
| Design | What is varied, controlled, and compared against which baseline? |
| Decision rule | Which primary metric and threshold/direction supports or contradicts the hypothesis? |
| Alignment | Which literature/repository protocol becomes the method and what remains out of scope? |
| Seed cards | Which 0–3 existing runs should enter backlog without migrating all history? |

Stop with 1–2 methods that define comparison, control, measurement, and
interpretation, plus 0–3 seed cards. Run prose review and confirm the complete
causal chain. Add method framing to the brief without module names.

Target v1 depth: one problem, 1–2 causes, 1–2 hypotheses, 1–2 methods, and
0–3 seed cards. Use **koi-grill-experiment** for detailed future cards.

Before Section 5, assemble the complete brief. It becomes `onboard-brief.md`
during writing and is already the ANCHOR for title refinement.

## 5. Cold-reader clarity loop (titles only)

After confirming the skeleton and receiving permission to polish/write, test
**only** node/card/program titles with a cold reader. Descriptions and `desc`
are out of scope. Goal: map titles are understandable without drifting from the
high-level scientific framing. Maximum six iterations.

### ANCHOR: onboard-brief.md

Before every title revision, the Writer rereads the complete current brief. Do
not send it to the cold reader.

Allowed: clarify the phenomenon, mechanism, or intervention idea at the same
abstraction level. Prohibited: replace a research problem with pipeline steps,
frame/debugging details, or an engineering task list.

Bad drift:

```text
problem: Model cannot group puzzle shapes
cause: Shapes are not grouped in simplified frames
remediation: Pipeline: tracking → relationships → importance
method: Full pipeline versus segmentation
cards: Debug tracking; link matching shapes; add importance
```

Good high-level framing:

```text
problem: Models fail in abstract visual reasoning
cause: No model for reasoning over abstract scenes
remediation: Human Gestalt and attention rules
method: World model using Gestalt and attention
```

Cards may be more concrete than methods but must not pull problem/cause down
into implementation debugging.

### Roles and snapshot

| Role | Behavior |
|------|----------|
| **Writer** | Onboarding agent edits titles only, keeps ANCHOR, gives no explanation to the cold reader |
| **Cold reader** | New read-only subagent sees titles only and knows no brief/repository/dialogue |

Snapshot:

```text
problem: <title>
  cause: <title>
    remediation|cause_evidence: <title>
      method: <title>
        cards: <card title>, …
program: <title>
project_title: <frontmatter title>
```

No descriptions, code, literature, ANCHOR, or explanations.

### Iteration 1..6

1. Writer rereads ANCHOR and prepares `T_i`.
2. Launch a read-only `generalPurpose` subagent named `KOI titles cold read`:

```text
You are a cold reader. You know nothing except the TITLE tree below.

Which titles are unclear, ambiguous, or too jargon-heavy on a map?
Do not request implementation details, pipelines, module names, or descriptions.
Keep titles as research claims: phenomenon, mechanism, intervention idea, method.

Output:
Line 1: CLEAR or UNCLEAR
If CLEAR: one sentence; clarity 1-10; laconicism 1-10.
If UNCLEAR: Title | What is unclear | What would help
Do not rewrite.

Titles:
<paste T_i only>
```

3. Stop early on `CLEAR`, clarity ≥8, laconicism ≥7.
4. On UNCLEAR, Writer edits titles only, runs the anchor check below, then submits
   `T_{i+1}`. Do not compensate with descriptions or chat explanation.
5. Limit titles to eight words. A critical title may use up to 12 only after two
   failed eight-word attempts.
6. Run prose self-check after every edit.

### Anchor check after every Writer edit

Reject a candidate on any “no”:

1. Is problem still the agreed field phenomenon rather than frames/pipeline/debugging?
2. Is cause a mechanism rather than a dataset simplification or tracker bug?
3. Is the hypothesis the agreed intervention/prediction rather than a module list?
4. Is method an evaluation protocol rather than “full pipeline vs segmentation”?
5. Can every title be mapped to ANCHOR in one sentence?

Choose the best `T_1…T_k` by clarity, laconicism, ANCHOR fidelity, and fewest
9–12-word exceptions. Discard drift even when cold reader says CLEAR.

Keep descriptions from the dialogue and align them outside the clarity loop.
Tell the user how many iterations ran and which titles changed. If iteration six
remains UNCLEAR without drift, show feedback and ask the user. Do not write
without permission.

## 6. Final prose pass and writing

Proceed only after the user says “write” or “create.”

### 6a. Full prose pass

Collect visible fragments from the best title set:

- frontmatter `title` and `description`;
- every node title and description;
- seed-card titles and `desc`.

Review the complete set for consistency with **koi-prose-style**. Titles marked
as clarity exceptions may use 9–12 words; all others use at most eight. Continue
to 6b only on PASS. After three failures, show feedback and ask; do not write
without explicit permission.

### 6b. Write canonical files

Create:

```text
tree/<repo>/koi-structure/
  project.md
  onboard-brief.md
  research.json          # {"version": 1, "questions": []}
  reports/               # empty or .gitkeep
```

`tree/` is a sibling of the engine and `<repo>` is the code-folder name. Do not
write `<repo>/koi-structure/` when canonical tree storage is available.

Write `onboard-brief.md` before or with `project.md`, aligned with the final
titles. Remove any `.koi-onboard-brief.draft.md`.

### project.md frontmatter

```yaml
---
id: <agreed-kebab-case-id>
title: <short problem title after prose pass>
description: <1–3 sentences after prose pass>
updated: <ISO-8601 Z>
format: koi/1
git_repo: true                    # when <repo>/.git exists
git_sync_branch: koi/research     # default unless user chooses another
programs:                         # omit for explicit no-program decision
  - id: <program-id>
    title: <title at most 8 words>
---
```

For a git repository, always set `git_repo: true` and `git_sync_branch`, or the
sync CLI will not discover the mount.

### Tree format

- Headings: `# problem: <id>`, `## cause: <id>`, `### remediation:` or
  `### cause_evidence:`, and `#### method: <id>`.
- Use concise technical ids; visible text remains natural prose.
- Add a kanban table under each method:

```markdown
<!-- koi:kanban board-<method-id> -->
| backlog | running | done | successful |
| --- | --- | --- | --- |
| <readable title> <!-- id:<card-id> desc:<experiment output; script path at end if needed> --> |  |  |  |
```

- Do not set cause `verdict:` during onboarding; default is open.
- Node prose must be both testable and natural.
- Node/card titles use at most eight words; put all details in description/desc.

### Pre-write checklist

- [ ] No existing project.md unless the user explicitly requested an addition
- [ ] Layers 3A → 3PROG → 3B → 3C pass
- [ ] programs decision recorded
- [ ] onboard-brief.md agrees with the dialogue
- [ ] Title-only clarity loop completed within six iterations without drift
- [ ] Every node passes framing-checks
- [ ] koi-prose-style PASS on all visible skeleton fragments
- [ ] Titles at most eight words, or valid critical exceptions at most 12
- [ ] No mixed-language or log-status titles
- [ ] One problem, at most two causes/hypotheses/methods unless explicitly expanded
- [ ] Method is a comparison protocol, not a feature name
- [ ] research.json is valid JSON
- [ ] git_repo/git_sync_branch match `.git` presence

After writing, continue immediately to 6c for git repositories. For a non-git
folder, report the path/id/UI next step.

### 6c. Layout and orphan branch

For `<repo>/.git` with `git_repo: true`, store research data on the orphan
`git_sync_branch` (default `koi/research`) and attach it under `tree/<repo>/` as
a worktree. Do not change git config or commit secrets.

From the engine root:

```bash
python -m koi.projects.install_cli install <repo>
python -m koi.projects.sync_cli push --project-id <id> \
  --message "projects(<id>): onboard skeleton tree"
python -m koi.projects.sync_cli status
```

`install_cli` creates the orphan branch when needed, attaches the worktree,
adds code-branch ignores, and migrates legacy `koi-structure` layouts.

If install/push fails because of origin, permissions, or non-fast-forward:

- show stderr;
- never force;
- ask the user to repair remote/permissions and rerun install/push;
- retain the valid local `tree/<repo>/koi-structure/`; do not roll it back.

Final response states project.md path, project id, orphan branch, install/push
result or error, and which UI URL to open after restarting when needed.

## 7. Handoff

| Next work | Skill |
|-----------|-------|
| Detail a card before execution | **koi-grill-experiment**; reread onboard-brief before new titles |
| Execute a card | **koi-execute-card** |
| Long remote role-based run | **koi-card-autoresearch** plus project launch skill |
| Further sync | **koi-project-sync** / `sync_cli push|pull` |
| Layout/migration only | `install_cli install|migrate <repo>` |
| Full Related Work | literature-review agent / paper pipeline |

Before any later `project.md` title edit, reread `onboard-brief.md`.

## Out of scope for v1

- Automatically creating a program in the UI
- Migrating historical reports or experiment-tracker runs to done
- Replacing an existing tree
- Full BibTeX/Introduction/citation review
- Force-pushing orphan or code branches

## Related references

- Brief template: [onboard-brief.template.md](onboard-brief.template.md)
- Mandatory prose gate: `agents/skills/koi-prose-style/SKILL.md`
- Layout install/migrate: `python -m koi.projects.install_cli`
- Orphan sync: `python -m koi.projects.sync_cli` and `koi-project-sync`
- Discovery: `docs/adr-001-project-discovery.md` and AGENTS.md Layout
- Human attach guide: README Add a project and `docs-site/start/with-code.html`
- Tree format: `docs/human/project-format.md`
- Node glossary: `docs/human/getting-started.md`
- Card grill: `agents/skills/koi-grill-experiment/SKILL.md`
