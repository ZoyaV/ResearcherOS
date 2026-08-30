# Agents in ResearchOS

ResearchOS is designed for research tasks performed by agents in different
environments, including Cursor, Codex, and Claude. Shared repository instructions
are in [`AGENTS.md`](../AGENTS.md), and substantive skills are in
[`agents/skills/`](../agents/skills/).

## Project layout

```text
workspace/
├── ReseachOS/                         # engine
├── tree/<repo>/koi-structure/         # research (koi/research branch)
└── <repo>/                            # code (any branch)
```

Install or migrate with `python -m koi.projects.install_cli install <repo>`.
Discovery enters the `tree` directory and searches for `*/koi-structure/project.md`.

## Sources of truth

| Entity | Location |
|---|---|
| Research tree and kanban | `tree/<repo>/koi-structure/project.md` (legacy: `<repo>/koi-structure/`) |
| Research findings | `…/koi-structure/research.json` |
| Public and working reports | `…/koi-structure/reports/` |
| Curated knowledge | `…/koi-structure/knowledge/*.md` |
| Generated knowledge index | `KNOWLEDGE.md`, updated by `koi/knowledge` |
| Substantive agent skills | `agents/skills/` |

## Skills

- `koi-project-onboard` — attach a code repository through dialog + prose + a tree
  in `tree/<repo>/koi-structure/`, followed by `install_cli` (orphan `koi/research`);
- `koi-grill-experiment` — design an experiment card before a run;
- `koi-execute-card` — execute an experiment card;
- `koi-card-autoresearch` — run long research with Manager / Researcher / Debugger roles;
- `koi-report-review` — prepare and review a report;
- `koi-done-research` — formulate the conclusion of a completed experiment;
- `koi-agent-chat` — answer a question from the UI;
- `koi-knowledge-curator` — synthesize accumulated knowledge;
- `koi-paper` and `koi-related-work` — prepare paper materials;
- `koi-project-sync` — synchronize `tree/<repo>/koi-structure` with the sync branch;
- `koi-prose-style` — review human-readable text.

Templates and rules live beside the skill that uses them. There is no separate
global standards directory.

## Cursor

The local, gitignored `.cursor/` directory only integrates the IDE:

- `.cursor/hooks.json` — copy from [`agents/cursor-hooks.json`](../agents/cursor-hooks.json);
- `.cursor/skills/<name>` — symlink to `agents/skills/<name>` without copying.

The hooks themselves live beside the skills:

| Skill / location | Hooks |
|---|---|
| `agents/hooks/` | `koi-session-start.sh` (starts the API) |
| `agents/skills/koi-agent-chat/hooks/` | session / stop → UI chat queue |
| `agents/skills/koi-done-research/hooks/` | session / stop → done-research queue |
| `agents/skills/koi-project-sync/hooks/` | session / stop → pull / push reminders |

Product developer skills, such as channel news, remain only in local
`.cursor/skills/` and are not placed in `agents/skills/`; see [`AGENTS.md`](../AGENTS.md).

Substantive skills are in [`agents/skills/`](../agents/skills/).

Learn more in the [research workflow](research-workflow.md),
[domain model](domain-model.md), [Inbox guide](agent-chat-inbox.md),
[ADR-001 discovery](adr-001-project-discovery.md).
