# AGENTS.md — the IDE agent as a staff researcher

This repository is designed to be cloned by people using an agentic IDE such as
Claude Code, Cursor, or Codex. Here, the agent is not an auxiliary tool but the
**default executor** for research tasks: running experiments, writing reports,
formulating findings, and curating the knowledge base. Deterministic rules in
`koi/projects/report_ingest/` and `koi/knowledge/` only provide transport: they
validate the format and idempotently ingest what the agent produced. Analysis and
synthesis always belong to the agent.

The substantive playbooks live in `agents/skills/*/SKILL.md`; Cursor sees the same
directories through links in `.cursor/skills/`.

When adding a new skill, use the developer skill
`.cursor/skills/koi-add-research-skill`. A substantive research skill is stored
once in `agents/skills/`, while `.cursor/skills/` receives only a relative link if
needed. Skills for developing ResearchOS itself remain in `.cursor/skills/` and
are not duplicated in `agents/skills/`.

## Session start — check the queues

1. **done-research** (cards moved to done and awaiting a conclusion): run
   `python -m koi.projects.done_research_cli pending`; if the list is not empty,
   process each item using `agents/skills/koi-done-research/SKILL.md`.
2. **agent-chat** (questions from the Ask Agent UI panel): the queue is
   `.run/agent-chat-queue.json`; use the playbook in
   `agents/skills/koi-agent-chat/SKILL.md`.

## Project layout (required)

Canonical layout (ADR-001):

```text
workspace/
├── ReseachOS/                         # engine (this repository)
├── tree/
│   └── <repo>/koi-structure/          # research materials, koi/research branch
└── <repo>/                            # experiment code, any branch
```

- Discovery: if a directory is named `tree`, search the next level for
  `*/koi-structure/project.md`. Legacy `<repo>/koi-structure/` is still supported.
- Resolve tree/report/knowledge-base paths through the mount
  (`tree/<repo>/koi-structure/…`); do not assume `koi-structure` lives inside the
  code repository.
- Install or migrate the layout:

```bash
python -m koi.projects.install_cli status
python -m koi.projects.install_cli install <repo>          # or migrate
python -m koi.projects.install_cli install <name> --create # empty project
```

## Workflows

| Task | How |
|--------|-----|
| Attach an existing code repository to ResearchOS | Use **koi-project-onboard**: dialog → brief → clarity → prose → write to `tree/<repo>/koi-structure/`; then run **`install_cli install <repo>`** (orphan `koi/research` + tree worktree) |
| Create only the layout / koi/research branch without onboarding | `python -m koi.projects.install_cli install <repo>` |
| Synchronize research data | Use **koi-project-sync** / `sync_cli push|pull` (working copy = `tree/<repo>/koi-structure`) |
| Design a new experiment before a run | Use **koi-grill-experiment** for a one-question-at-a-time interview with recommendations on framing, implementation, tables/plots, and done criteria; then draft §§1–3 and use **koi-report-review** |
| Execute a kanban card | Use **koi-execute-card**: **first** move `backlog` → `running`, mark `- [x]` in §3 “Subtasks” **immediately** as work completes, and finally move `running` → `done`; then use **koi-done-research** |
| Long run / autonomous research (Manager → Researcher → Debugger) | Use **koi-card-autoresearch** for roles and cadence on top of **koi-execute-card**; a project-specific skill such as `verl-experiment-run` supplies launch scripts |
| Test a hypothesis (kanban card) | Run `python -m koi.projects.report_ingest.cli <project_id> <card_id>`. If the server backend is unavailable, as is common in a clone, **perform the agent work yourself** with **koi-execute-card**: run the experiment, fill `agents/skills/koi-report-review/experiment-report.md` → `projects/<id>/reports/<node>/<card>.run.md` (use **koi-report-review**, critic 4), then run `… --ingest-only` (first with `--dry-run`). Apply **koi-report-review** to the public skeleton report at every phase |
| Conclude a done card | Use `koi-done-research`; write question/narrative in plain language and metrics in `answer` |
| Answer a UI question | Use `koi-agent-chat`; inspect `research.json` first and reports only when details are missing |
| Deep knowledge synthesis | Use `koi-knowledge-curator` for cross-analysis of reports and insights, producing curated documents in `projects/<id>/knowledge/` |
| Cards, descriptions, and human-readable text | Use `koi-prose-style`: draft → subagent review → rewrite until PASS → write to the file |
| Experiment report (framing / results) | Use `koi-report-review`: critics 1–3 for §§1–3 and critic 4 for §4+ / `.run.md` |

## Format gates (rules the agent must not bypass)

- A `.run.md` report must contain §0 “References” with real IDs in backticks, a
  §5.1 verdict line in the form
  `` `<cause-id>` → … **supported|refuted|open** ``, and exactly one fenced
  ```json block in §5.2 with no more than three insights. An invalid report is
  rejected as a whole and changes nothing.
- Re-ingesting the same report is a no-op. Editing and re-ingesting a report
  replaces only that card's insights.
- Do not edit generated files (`KNOWLEDGE.md`, `knowledge/hypotheses.md`,
  `KNOWLEDGE_LOG.md`) manually or through an agent; they will be overwritten.
  Curated knowledge belongs only in `projects/<id>/knowledge/<custom-file>.md`.
- Define the decision rule (supported if…; refuted if…) **before** the run. A
  verdict substitutes measured values into the rule; it is not based on an
  impression.
- Tree-node and kanban-card titles must contain **no more than eight words**.
  Put details only in the node description or card `desc` (`koi-prose-style`).

## Onboarding and reference

- Layout + install CLI: `python -m koi.projects.install_cli` · ADR
  `docs/adr-001-project-discovery.md` · README § «Add a project».
- Attach a code repository with the agent: use `koi-project-onboard` at
  `agents/skills/koi-project-onboard/SKILL.md` (writes to
  `tree/<repo>/koi-structure/`).
- Complete newcomer path: `docs/human/getting-started.md`.
- Domain model: `docs/domain-model.md`.
- Documentation: `docs/README.md`; public site: `docs-site/start/`.
- Knowledge accumulation process and review matrix: `docs/research-workflow.md`.
- UI Inbox chat: `docs/agent-chat-inbox.md`.
