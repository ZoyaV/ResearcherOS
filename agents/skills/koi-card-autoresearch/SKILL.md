---
name: koi-card-autoresearch
description: >-
  Orchestrate a long-running ResearchOS kanban experiment with three agent
  roles (Manager, Researcher, Debugger): start the card, run and monitor the job,
  triage failures, and keep report Section 3 and kanban synchronized through
  koi-execute-card. Trigger when the user asks for systematic card research,
  autoresearch, card-autoresearch, or a manager/researcher/debugger cadence on a
  card. For short one-shot runs, use koi-execute-card.
---

# KOI: card autoresearch

This is a long-running experiment for **one** kanban card with separated roles.
**koi-execute-card** remains authoritative for kanban, Section 3, and reporting;
this skill adds orchestration: who starts, who runs and watches the job, and who
only diagnoses failures.

Use **koi-execute-card** for a short local experiment that can be completed in
one session. Use **koi-card-autoresearch** for multi-hour or remote work that
needs scheduled debugging.

## Difference from koi-execute-card

| | koi-execute-card | koi-card-autoresearch |
|--|------------------|------------------------|
| Ownership | One agent performs all steps | Three roles with different write permissions |
| Duration | Minutes to hours in one session | Hours to days with watch/debug loops |
| Failures | Same agent fixes them | Debugger recommends; Researcher fixes |
| Launch details | Any | Uses project-specific scripts/skills when available |

A project-specific implementation might be `verl-experiment-run` for remote
CrafText/verl jobs. ResearchOS itself contains no GPU scripts, only roles and
cadence.

## Trigger

Examples: **“Run systematic research for card …”**, **“Run autoresearch for
card …”**, **“card-autoresearch”**, or “start with monitoring and a debugger.”
Do not collapse these requests into one short koi-execute-card pass; run the
complete role cycle.

## Three roles

| Role | Does | Does not |
|------|------|----------|
| **0. Manager** | Moves one card to `running`; configures live fields and state JSON; hands off to Researcher | Launch jobs or edit experiment code |
| **1. Researcher** | Starts the job through project scripts; watches it; checks Section 3 tasks; calls Debugger; finishes as `done` | Change unrelated code without explicit human approval |
| **2. Debugger** | Triages logs/sysmon and writes advice to `state.debugger` | Edit files or restart jobs |

Playbooks: [manager.md](agents/manager.md),
[researcher.md](agents/researcher.md), and [debugger.md](agents/debugger.md).

## Default cadence

| Actor | Frequency | Purpose |
|-------|-----------|---------|
| Manager | Once at the beginning | Card, live view, state |
| Researcher watch | Every minute × 20, then every 20 minutes | Job pulse, `live_note`, debugger calls |
| Debugger | Every 10 minutes and immediately at launch | Scheduled triage |
| Debugger | On Researcher request | Early failure; do not wait for schedule |
| sysmon (not an agent) | About every 60 seconds when possible | GPU/RAM/disk or equivalent |

The project-specific skill defines shell scripts and log paths. Without one, the
Researcher maintains the cadence with IDE timers or a loop skill and updates
`live_note` manually.

## Quick start

```text
User: “Run systematic research for card <id>”

Manager:
  1. Find card → backlog → running (koi-execute-card)
  2. Configure live fields + state/<project>-<card>.json
  3. Update the user and hand off to Researcher

Researcher:
  1. Use a project launch skill when available, otherwise run locally
  2. Watch on cadence; call Debugger on failure
  3. Read state.debugger.pending_recommendation; fix or restart
  4. Check completed tasks; write report; running → done; koi-done-research
```

## ResearchOS live panel

The Manager writes these fields in the card description or report header, using
paths from the code-project root:

```text
live_log: projectcode/runs/live/train.log
metrics_dir: projectcode/runs/plots
live_note: started; waiting for first steps
live_sysmon: projectcode/runs/live/sysmon.log
compute_cost: wall_h=…; gpu_h=…; n_gpus=…; until=…; source=measured
```

While the card is `running`, the UI reads these paths from the method map. The
`compute_cost:` line is optional; fill wall/GPU hours when the job finishes.

## State file

Recommended path: `state/<project_id>-<card_id>.json`.

```json
{
  "project_id": "<id>",
  "card_id": "<id>",
  "training_status": "running",
  "researcher_watch": {
    "phase": "warmup",
    "tick": 0,
    "last_check": null,
    "last_summary": null
  },
  "debugger": {
    "last_check": null,
    "pending_recommendation": null
  }
}
```

Debugger writes to `debugger.pending_recommendation`. Researcher reads it during
watch, applies it or escalates to the user, then clears the pending field.

## Related skills

- **koi-execute-card** — required kanban / Section 3 / report / done framework
- **koi-report-review** — report quality during setup and results phases
- **koi-done-research** — after `done`
- **koi-project-sync** — after significant changes
- Project-specific example: **verl-experiment-run** for remote/sysmon/debug loops

## Prohibited

- Using two cards in one autoresearch run
- Debugger editing code or restarting a job
- Manager launching training
- Moving to done with incomplete Section 3 tasks unless the report explicitly
  records an open outcome or abandonment
