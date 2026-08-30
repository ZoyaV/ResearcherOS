# ResearchOS from scratch: from idea to knowledge base

An end-to-end guide built around one tutorial example, “Solving quadratic equations.”
It covers the complete cycle: create a project in the web interface → build a
hypothesis tree → add experiments to kanban → run an experiment → write a report →
automatically ingest the result into the knowledge base → inspect the outcome.

Canonical references (this guide links them together rather than replacing them):

| What | Where |
|-----|-----|
| Project and tree format | `docs/human/project-format.md` |
| Program format | `docs/human/program-format.md` |
| Complete knowledge-base design | `docs/human/knowledge-base.md` |
| Working report template (primary) | `agents/skills/koi-report-review/experiment-report.md` |
| Public report template | `agents/skills/koi-report-review/report-skeleton.md` |
| Report formatting rules | `agents/skills/koi-report-review/report-rules.md` |
| “Report → review → knowledge merge” process | `docs/research-workflow.md` |
| IDE agent instructions | `AGENTS.md` |
| Attach a repository with existing code | `koi-project-onboard` skill (IDE agent) |

---

## 0a. Existing code — attach a repository

Place the code repository beside `ReseachOS/` and install the layout:

```bash
cd ReseachOS
python -m koi.projects.install_cli install <repository-directory-name>
# → tree/<repo>/koi-structure/  (koi/research branch)
#    <repo>/                    (code, any branch)
```

If no hypothesis tree exists yet, ask the IDE agent:

> Connect `<path-to-repository>` to ResearchOS

Using **`koi-project-onboard`**, the agent conducts an interview and writes
`tree/<repo>/koi-structure/project.md` plus `onboard-brief.md`. An existing tree
is never overwritten.

Continue with the steps below; use `koi-grill-experiment` to develop card details.

---

## 0. Fastest start — create a tutorial project

For your first pass, create a small tutorial project whose experiment can run with
one local command. For example, compare two ways to solve quadratic equations by
speed and accuracy:

> **📘 Example: solving quadratic equations** (program “📘 Example: quadratic equations”).
> This is a demonstration, not a working project—**open nodes and cards and click
> anything you like; you cannot break it.**

What to inspect, one click at a time:

1. **Hypothesis map.** Two branches extend from the problem:
   - “Grid search is fundamentally inefficient” has a green ✔ badge (the
     hypothesis is **supported**);
   - “A naive discriminant loses accuracy for large b” has **no badge** (the
     hypothesis remains **open** and untested). This is an unfinished branch.
2. **Completed report.** The “Vieta solver versus grid search” method has a card
   in **done**. Click it to see a **fully written report** with the run, numbers,
   and conclusion—the target form for a completed report.
3. **Empty card = ready template.** Click a **backlog** card for the same method.
   The editor opens a **prefilled template** with IDs and date already inserted;
   only the results remain to be added. This is how your own experiment starts.
4. **Knowledge base.** Click **Knowledge Base** in the toolbar and select this
   project to see the hypothesis verdict, two quantitative insights, and a link
   to the source report.

After exploring the reference project, create your own with the steps below.

---

## 1. The main idea in 30 seconds

ResearchOS is “Agile for science.” Instead of “solution → tasks,” the cycle is:

```
PROBLEM → causes (explanatory hypotheses) → hypotheses (how to evidence/remediate)
   → TEST METHODS → experiment cards on kanban
   → EXPERIMENT REPORT → verdict + insights
   → KNOWLEDGE BASE (assembled automatically, without an LLM)
```

The key principle: **knowledge comes only from an experiment with a decision rule
defined in advance**. First write “the hypothesis is supported if metric X passes
threshold Y,” then run the experiment. The verdict follows by substituting the
numbers into the rule, not from a general impression.

Everything is stored in Markdown files without a database. One project is one
`projects/<id>/` directory; the web interface is a convenient editor for these files.

## 2. Starting and connecting

On a personal machine, run `scripts/koi-serve.sh start` to start the API on 8010
and UI on 8080, then open http://localhost:8080.

**On airi-5090**, ports 8010/8080 are occupied by another instance, so start yours manually:

```bash
# on the server, from the repository root
source .venv/bin/activate
nohup .venv/bin/uvicorn api.main:app --host 127.0.0.1 --port 8011 > ~/.cockpit-jobs/koi-api-8011.log 2>&1 < /dev/null &
( cd web && nohup python3 -m http.server 8081 --bind 127.0.0.1 > ~/.cockpit-jobs/koi-web-8081.log 2>&1 < /dev/null & )
curl -sf http://127.0.0.1:8011/health    # → {"status":"ok",...}
```

From your local machine, create a tunnel (the UI accesses the API strictly through local port 8010):

```bash
ssh -N -L 8090:127.0.0.1:8081 -L 8010:127.0.0.1:8011 airi-5090
# UI: http://localhost:8090    API Swagger: http://localhost:8010/docs
```

## 3. Glossary

| Concept | Meaning | Location on disk |
|---------|---------|--------------------|
| **Program** | Strategic direction grouping projects in the sidebar | `programs/<id>/program.md` |
| **Project** | One research problem = one tree on the map | `projects/<id>/project.md` |
| **Problem** (`problem`) | Tree root: what is wrong | `# problem:` heading in project.md |
| **Cause** (`cause`) | Hypothesis about the *nature* of the problem. **Verdicts belong here** | `## cause: n-…` |
| **Hypothesis** (`cause_evidence` / `remediation`) | How to *evidence* the cause / how to *remediate* it | `### remediation: n-…` |
| **Method** (`method`) | Concrete test procedure with a kanban board | `#### method: n-…` |
| **Kanban card** | One experiment (backlog → running → done) | table under the method |
| **Report** | Experiment details | `projects/<id>/reports/<node>/<card>.md` |
| **Insight** | Quantitative Q&A, an experiment finding (≤3 per method) | `projects/<id>/research.json` |
| **Project knowledge base** | Automatically assembled contents: verdicts, insights, documents | `projects/<id>/KNOWLEDGE.md` + `knowledge/` |

The tree hierarchy is strict: problem → cause → (cause_evidence | remediation) → method.
The UI prevents invalid placement: the dotted Add circle below each node offers
only allowed child types.

## 4. Step 1 — create a program and project in the UI

1. Open the UI. A `<` / `>` chevron at the left edge expands the **program and
   project sidebar**.
2. Click **+ New program** at the bottom of the sidebar and name it, for example,
   `Solving quadratic equations`. A group appears in the sidebar and
   `programs/solving-quadratic-equations/program.md` appears on disk.
3. Click **+** beside the program heading to create a **new project inside the
   program**. Use the problem statement as the project name, for example,
   `Computational complexity of exhaustive search`. A project without a program
   appears in the “No program” group.
4. The project opens on the map with one oval Problem node. On disk, the
   `projects/computational-complexity-of-exhaustive-search/` directory contains
   `project.md`, `research.json`, and an empty knowledge base.

> Project/node IDs are generated automatically (`n-1a2b3c4d`, `c-1a2b3c4d`, …).
> Reports need them; see §7.2 for where to find them. Specific IDs below such as
> `n-ce100001` come from the **reference example** (§0), which you can open for comparison.

## 5. Step 2 — develop the tree (what to write in nodes)

A dotted **Add +** circle under every map node creates a child of an allowed type:
Add cause → Add evidence or hypothesis → Add method. Clicking a node opens a panel
where Edit changes the title and description, Save/Cancel finish editing, and
Delete node appears at the bottom.

The first line is a short title (**no more than eight words**, visible on the map),
followed by a detailed description shown when the node opens. The main rule:
**a node must be a testable claim, not a topic**. “Analytics” is weak; “The formula
is faster and more accurate than exhaustive search,” with time and residual
thresholds in the description, is strong.

Example content for this project:

**Problem** (the root, created with the project):

> Computational complexity of exhaustive search
>
> Solving ax²+bx+c=0 by numerically enumerating candidates requires enormous
> numbers of evaluations and still does not guarantee accuracy. We want to
> understand why exhaustive search is fundamentally poor and what should replace it.

**Cause** (Add cause below the problem) — a hypothesis about the nature of the
problem, phrased so it can be supported or refuted:

> Infinitely many candidates to search
>
> Roots lie in a continuous space: every finite candidate grid either misses the
> root or requires an astronomical number of evaluations. Supported if, on random
> equations, a reasonable grid loses to the analytical method in both speed
> (≥100×) and accuracy (orders of magnitude in residual).

**Hypotheses** (below the cause, Add evidence or hypothesis) — possible remediations:

> Analytical solution
>
> Closed-form expressions (the discriminant and Vieta's formulas) provide both
> roots in O(1) at machine precision, eliminating exhaustive search entirely.

> Advanced solver
>
> Existing numerical solvers (numpy.roots via eigenvalues of the companion matrix)
> solve the problem without manual enumeration and scale to higher degrees.

**Method** (below a hypothesis, Add method) — a concrete test procedure that gets
its own kanban board:

> Vieta's formulas
>
> Implement a solver using x1+x2=−b/a and x1·x2=c/a (plus the discriminant for
> the roots), then compare it with grid search on a batch of random equations:
> time for 1,000 equations and residual |f(x)|.

When results arrive, verdict badges (✔/✗) appear on causes/hypotheses. The method
shows a `tot · proc · done` kanban summary with a progress bar.

## 6. Step 3 — create experiments on the method kanban

Click a method node to open its kanban section with **backlog / running / done**
columns. The **+** button in each column heading adds a card. Drag cards between
columns; the column is the experiment status.

A card represents one experiment with a clear outcome. For this method:

| Column | Card |
|---------|----------|
| backlog | `Compare the Vieta solver with grid search on 1,000 random equations` |
| backlog | `Test numerical stability for a≈0 and large b (catastrophic cancellation)` |

A good card title makes both the action and measurement clear. “Test Vieta's
formulas” is weak; “Compare with exhaustive search on 1,000 equations: time and
residual” is specific enough.

When starting an experiment, move its card to `running`. You do not need to move
it to `done` manually; automatic report integration (§8) does that.

## 7. Step 4 — run the experiment and write the report

This is the heart of the system. An experiment result enters the knowledge base
**only through a report** in a strict form: a working `.run.md` based on
`agents/skills/koi-report-review/experiment-report.md`. There are two ways to fill it.

### 7.1 Path A — the agent runs the experiment (one command)

```bash
# on the server, from the repository root, in .venv
python -m koi.projects.report_ingest.cli <project_id> <card_id>
```

The script assembles the project context (problem→cause→hypothesis→method chain),
gives the agent a task specification with a report template, waits for `.run.md`,
and automatically integrates it (verdict, insights, card → done, knowledge base).
Useful flags:

| Flag | What it does |
|------|------------|
| `--backend claude` / `--backend cursor` | which agent to use (by default, the order from `KOI_AGENT_BACKEND`; default value: `claude,cursor`) |
| `--no-ingest` | generate the report without integrating it (for manual review) |
| `--dry-run` | show what integration would change without touching files |
| `--timeout 1800` | agent time limit in seconds |

Backend requirements: the Claude Code CLI (`claude login` or `ANTHROPIC_API_KEY`),
or a Cursor API key. You can conveniently save the latter through the UI:
**Settings** in the toolbar → **Cursor API key** (stored in `KOI/.env`, excluded
from Git). To see which backends are available, call `GET /agent/backends`.

If no server backend is available (the usual case for a locally cloned repository),
your **IDE agent** (Claude Code, Cursor, or Codex) performs the same work by
default: open the repository in the IDE, and the agent follows `AGENTS.md` to run
the experiment, fill in `.run.md`, and ingest it with `--ingest-only`. Playbooks:
`agents/skills/*/SKILL.md`.

The same mechanism is available in the UI: click **Ask agent** in a node panel;
the question enters the agent-chat queue and the answer appears in the panel.

### 7.2 Path B — run the experiment and write the report yourself

The easiest option is through the UI: click a kanban card and the report editor
opens with a **pre-filled template**. The real hypothesis, method, and card IDs,
as well as today's date, are already inserted (the line below the editor title
identifies it as a template). Fill in the sections using the example below and
click **Save**. If you write the file manually outside the UI, first find the node
and card IDs. The easiest way is to open `projects/<id>/project.md`: IDs appear in
node headings and card comments. For the reference example (§0):

```markdown
## cause: n-ce100001           ← hypothesis “Grid search is inefficient”
#### method: n-ce100003        ← method “Vieta solver versus exhaustive search”
| … Compare speed and accuracy… <!-- id:c-ce100010 … --> |   ← card (done)
```

Next, copy the `agents/skills/koi-report-review/experiment-report.md` template to
`projects/<id>/reports/<Node title>/<Card title>.run.md` (spaces in names → `_`)
and fill it in. Remove the hint lines beginning with `>`.

Three places are critical for automatic integration:

1. **§0 “Links”** — real IDs in backticks: hypothesis (`n-ce100001`), method
   (`n-ce100003`), and card (`c-ce100010`).
2. **§5.1** — a verdict line in exactly this form:
   `` `<cause-id>` → … **supported** `` (or `refuted` / `open`). The verdict is
   attached to a Cause node; the knowledge-base dashboard calculates progress
   from causes. You may specify another node ID, but integration will warn you
   and it will not appear in the progress chips.
3. **§5.2** — **exactly one** fenced ```json block containing an array of **no
   more than three** insights.

Below is an illustrative report for this tutorial experiment. Substitute your own
command and the numbers you actually obtain.

````markdown
# Report: Vieta versus grid search on 1,000 random equations

## 0. Links

| Field | Value |
|------|----------|
| Hypothesis (cause) | `n-ce100001` — grid search is fundamentally inefficient |
| Method / card | `n-ce100003` / `c-ce100010` |
| Hypothesis specification | decision rule recorded before the run (see §3) |
| Run date | 2026-06-12 |
| Executing agent | Claude (reference example) |
| Run status | completed successfully |

## 1. What was run (reproducibility)

- Command: `<your tutorial experiment command>`
- 1,000 equations ax²+bx+c=0: a∈[−10,10]\{0}, b,c∈[−100,100], seed 42; 864 have real roots
- Analytical method: discriminant + quadratic formula, with Vieta self-check (x1+x2=−b/a, x1·x2=c/a)
- Exhaustive search: grid x∈[−200,200], step 1e−2 (40,001 candidates per equation), root = midpoint of an interval where f(x) changes sign
- Hardware: one thread, pure Python (without numpy)

## 2. Primary metric and results

| variant | time for 1,000 equations | accuracy | roots found |
|---------|-------------------|----------|----------------|
| analytical (Vieta) | 0.000164 s | max residual 7.7e−11; Vieta self-check: 0 discrepancies | 100% (1728/1728) |
| grid search | 2.015 s | root error up to 5.0e−3 (half a grid step) | 96.9% of equations complete; 27 roots outside the grid (3.1% of equations) missed |

In one sentence: the analytical method is 12,271× faster than exhaustive search
and about eight orders of magnitude more accurate; the search found everything
inside its grid (1701/1701), but silently missed 27 roots outside [−200,200].

## 3. Decision-rule check

- Rule (recorded before the run): **supported** if the analytical method is ≥100× faster AND residual <1e−9 for ≥99% of equations; **refuted** if exhaustive search is ≤10× slower at comparable accuracy; otherwise **open**.
- Result: 12,271× speedup (threshold: 100×); residual <1e−9 for 100% of equations (threshold: 99%).
- → The rule yields: **supported**

## 4. Threats and caveats (what this run does NOT prove)

- The exhaustive search is naive: an adaptive grid or bisection would narrow the timing gap, but not to the 10× threshold, and would not solve the out-of-range root problem.
- A 1e−2 step is a compromise: a finer grid is more accurate but even slower. It does not affect the verdict because the gap is already four orders of magnitude.
- Catastrophic cancellation when b²≫4ac is not covered here; it is tracked in a separate hypothesis (`n-ce100020`).

## 5. Knowledge-base proposal

### 5.1 Proposed verdict for the cause node

- `n-ce100001` → by the rule in §3: **supported**
- Rationale: exhaustive search was 12,271× slower, eight orders of magnitude less accurate, and missed 3.1% of roots (§3).

### 5.2 Proposed insights (≤3 per method, research.json format)

```json
[
  {
    "method_id": "n-ce100003",
    "card_id": "c-ce100010",
    "question": "How much faster and more accurate is the analytical solution than grid search?",
    "answer": "1,000 equations, seed 42: 0.000164 s vs 2.015 s (12,271×); residual ≤7.7e−11 vs error up to 5e−3",
    "narrative": "The quadratic formula solves a thousand equations in fractions of a millisecond versus two seconds for exhaustive search, with eight orders of magnitude greater accuracy.",
    "certainty": "definite",
    "importance": 4
  },
  {
    "method_id": "n-ce100003",
    "card_id": "c-ce100010",
    "question": "Where does exhaustive search on a fixed grid miss roots?",
    "answer": "27 roots (3.1% of equations) lie outside [−200,200]; as |a|→0, roots of order |b/a| exceed any fixed boundary",
    "narrative": "A fixed grid silently misses roots beyond its boundaries; exhaustive-search methods need an adaptive search domain.",
    "certainty": "tentative",
    "importance": 3
  }
]
```

### 5.3 Integration recommendation

- Recommendation: accept as is.
- Why: both rule thresholds were exceeded by a wide margin; the caveats in §4 are covered by a separate hypothesis.
````

## 8. Step 5 — integrate the report into the knowledge base

A completed report is ingested with one command (you can start with `--dry-run`):

```bash
python -m koi.projects.report_ingest.cli quadratic-equation-example c-ce100010 --ingest-only
```

Without a path argument, `--ingest-only` reads the report from the expected path
(`reports/<node>/<card>.run.md`). If there is no `.run.md` but a public `.md` was
saved through the UI, that file is used. You can also pass a path explicitly:
`--ingest-only path/to/report.run.md`.

The following happens automatically (one pass, followed by the standard
`save_project` hook):

1. The **supported** verdict is attached to hypothesis `n-ce100001`, and a ✔ badge appears on the map.
2. Two insights are written to `research.json` and appear in the method panel under **Experiment findings** as **Definite answer** or **Tentative answer**.
3. Card `c-ce100010` moves to **done**, and an entry is added to `reports/index.json`.
4. `KNOWLEDGE.md`, `knowledge/hypotheses.md`, and the `KNOWLEDGE_LOG.md` journal are rebuilt.

Properties you can rely on:

- **Idempotence**: ingesting the same report again is an exact no-op. Edit the
  report and rerun it, and the insights for *that* card are replaced while all
  others remain untouched.
- **Rejection**: if §0 lacks links, §5.1 lacks a verdict line, or the JSON in §5.2
  is invalid (not exactly one block, more than three insights, or bad syntax),
  integration fails with a clear explanation of what to fix and **changes nothing**.

## 9. Step 6 — where to view accumulated knowledge

- **In the UI**: click **Knowledge base** in the toolbar to open the project
  contents (verdict chips, supported/refuted/open progress for causes, hypothesis
  cards with insights, and documents) and the **Update log** tab. ✔/✗ badges are
  visible directly on the map.
- **In files**: `projects/<id>/KNOWLEDGE.md` (contents with summaries),
  `knowledge/hypotheses.md` (generated list of all verdicts and insights with
  report links), and `KNOWLEDGE_LOG.md` (journal).
- **Your own knowledge documents**: place any `.md` in
  `projects/<id>/knowledge/`; it is picked up automatically. Convention: a
  `# Heading` followed by a first paragraph used as the contents summary. Do not
  edit generated files (`KNOWLEDGE.md`, `hypotheses.md`, `KNOWLEDGE_LOG.md`) by
  hand; they will be overwritten.
- **Via API**: `GET /projects/{id}/knowledge/summary` (also consumed by the dashboard).

## 10. Public report (when the result is worth sharing)

`.run.md` is the working layer with local paths and raw metrics. For an important
result, create a public `<card>.md` beside it using
`agents/skills/koi-report-review/report-skeleton.md` and the rules in
`report-rules.md` (no “AI markdown”; use public names instead of local paths).
In the UI, click a kanban card to open its report; images and videos from `assets/`
render directly in the report. Use the matrix in `docs/research-workflow.md` to
decide how an insight enters the knowledge base.

**Where to find the basis for verdicts and insights.** If there is no public `.md`
yet but the agent has finished, clicking the card opens its working `.run.md` (the
line under the heading shows the path, for example
`reports/Vieta_solver_versus_exhaustive_search/….run.md`). This is the primary
source for everything added to the knowledge base: the decision rule, numbers,
verdict, and JSON insights. Saving from this view creates a public version beside
it. `KNOWLEDGE_LOG.md` records what was added and when; in the UI, see **Update log**.

## 11. Checklist and common mistakes

Before running the experiment:
- [ ] The hypothesis is a testable claim, not a topic.
- [ ] **The decision rule was recorded BEFORE the run** (supported if…; refuted if…; otherwise open).
- [ ] The kanban card exists, and the node/card IDs are known.

Before integrating the report:
- [ ] §0: IDs in backticks are real and come from `project.md`.
- [ ] §3: the verdict follows from substituting the measured values into the rule.
- [ ] §5.1: a line of the form `` `n-…` → … **supported** ``, using a cause-node ID.
- [ ] §5.2: one ```json block, ≤3 insights, each with `method_id`, `card_id`, and numbers in `answer`.
- [ ] Use `certainty: definite` only when the threshold is exceeded by a margin and the conclusion is robust to §4.

Common pitfalls:
- A verdict based on intuition without a decision rule is rejected by the reviewer;
  the metric must meet a threshold from the specification.
- Multiple ```json blocks in §5.2 or more than three insights cause the entire report to be rejected.
- An insight without numbers in `answer` is useless for subsequent experiments.
- Manual edits to `KNOWLEDGE.md` or `hypotheses.md` are overwritten by the next
  `save_project`; curate content only in `knowledge/<your-file>.md`.

## 12. Quick reference

```bash
# all commands run on the server, from the repository root, in .venv (source .venv/bin/activate)

# have the agent test the hypothesis end-to-end (experiment + report + integration)
python -m koi.projects.report_ingest.cli <project_id> <card_id>

# same, but review the report before integration
python -m koi.projects.report_ingest.cli <project_id> <card_id> --no-ingest

# integrate your completed report; start with a dry run
python -m koi.projects.report_ingest.cli <project_id> <card_id> --ingest-only --dry-run
python -m koi.projects.report_ingest.cli <project_id> <card_id> --ingest-only

# self-check knowledge and report ingestion
PYTHONPATH=. .venv/bin/pytest -q tests/test_knowledge.py tests/test_report_ingest.py

# list available agent backends
curl -s http://127.0.0.1:8011/agent/backends
```

| I want to… | Where |
|-------|------|
| create a program/project | sidebar: **+ New program**, then **+** beside a program |
| add a node | dotted **Add +** circle under a map node |
| edit/delete a node | click the node → **Edit** / **Delete node** |
| create an experiment | method panel → kanban → **+** in a column |
| ask the agent | node panel → **Ask agent** |
| set the Cursor API key | toolbar → **Settings** |
| view knowledge | toolbar → **Knowledge base**; files in `projects/<id>/KNOWLEDGE*` |
| find the report format | `agents/skills/koi-report-review/experiment-report.md` |
