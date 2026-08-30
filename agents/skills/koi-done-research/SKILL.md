---
name: koi-done-research
description: >-
  When a KOI/ResearchOS kanban card moves to done, generate a method research
  question and answer with certainty (definite/tentative) and importance (1–5).
  Use when the user moves experiments to done, mentions done cards, or when
  the done-research queue has pending items.
---

# KOI: done → research conclusion

## When to run

1. The user moved an experiment card to **done** in the UI or through the API.
2. The queue contains unprocessed cards.
3. The user asks for a conclusion from a completed experiment.

At the start of a KOI/ResearchOS session, **check the queue first**:

```bash
KOI/.venv/bin/python -m koi.projects.done_research_cli pending
```

If it is non-empty, process every entry using the workflow below.

## Workflow for one card

### 1. Gather context

```bash
KOI/.venv/bin/python -m koi.projects.done_research_cli context \
  <project_id> <board_id> <card_id>
```

The JSON contains the method, parent hypothesis, card, report
(`report_markdown`), and existing `research_questions` (at most three per method).

### 2. Formulate the conclusion

Use the report, card description, and method context:

| Field | Purpose | Rules |
|-------|---------|-------|
| `question` | research question | One clear question that makes sense without project context. Avoid unexplained SFT/RL/PPO/diversity/SR and metric names; use plain descriptions such as “training on examples,” “simulator,” “share of successful attempts,” and “variety of actions.” |
| `narrative` | plain-language answer | Shown in the Conclusions modal; 2–4 sentences; an outside reader must understand it without a glossary. |
| `answer` | technical note | Raw metrics, steps, and abbreviations belong **only here**, not in question/narrative. |
| `certainty` | `definite` or `tentative` | A precise answer uses `definite`; a preliminary or uncertain answer uses `tentative`. |
| `importance` | integer 1–5 | Relative importance to the method: 1 is incidental, 3 is a moderate contribution, and 5 is a key answer. |
| `card_id` | kanban card id | **Required** for a conclusion from a done card; use `card_id` from the context JSON. |

**Certainty rubric**

- `definite`: the report has a done criterion, reproducible result, and an
  explicit yes/no answer or quantitative comparison.
- `tentative`: evidence is sparse or contradictory, metrics are intermediate,
  or the hypothesis was not fully tested.

**Importance rubric (1–5)**

- **5** — directly answers the method's main question or changes the proceed/stop decision.
- **4** — strong evidence for or against the hypothesis.
- **3** — useful clarification (default).
- **2** — weak signal or supporting detail.
- **1** — barely affects the method conclusion.

If a matching question already exists, **update** it using the same `id`; do not
create a duplicate. If all three slots are occupied, replace the least important
question or tell the user.

### 3. Save to ResearchOS

API (development server on port 8010):

```bash
curl -s -X PATCH "http://127.0.0.1:8010/projects/<project_id>/nodes/<method_id>" \
  -H "Content-Type: application/json" \
  -d '{"research_questions": [ ...all method questions, including the new or updated one... ]}'
```

Save the method node's **complete** `research_questions` list, not only the new
entry. On disk, questions are stored in `projects/<project_id>/research.json`,
not `project.md`.

### 4. Complete the queue item

```bash
KOI/.venv/bin/python -m koi.projects.done_research_cli complete \
  <project_id> <board_id> <card_id>
```

If no conclusion is possible because the report is empty or the card is not
done, still call `complete` and briefly explain why to the user.

## Example research question body

```json
{
  "id": "rq-new-001",
  "question": "Does the agent choose a wider variety of actions after training on example trajectories?",
  "narrative": "Yes. In the same situation, the model previously considered about one and a half action variants; after training it considered about two.",
  "answer": "mean diversity 2.02 vs 1.46 base (step 77)",
  "certainty": "definite",
  "importance": 5,
  "card_id": "kb-sft"
}
```

Before PATCH, review `question` and `narrative` with **koi-prose-style** using a
subagent until PASS. As a fallback, read them aloud: if the meaning is unclear
without the kanban and report, rewrite them.

## Queue

Moving a card to `done` adds it to `.run/done-research-queue.json`:

| Source | How it enters the queue |
|--------|--------------------------|
| UI drag-and-drop / API `PATCH column_id=done` | `save_project` → `sync_done_research_on_save` |
| Editing `project.md` on disk | `load_project` → `reconcile_done_research_queue` the next time the project is read |
| `report_ingest` with Section 5.2 | **Not queued** because the research question was already written from the report |

Skip the item when the method already has a `research_questions` entry with the
card's `card_id`.

### Cursor hooks

Scripts live in `agents/skills/koi-done-research/hooks/`. IDE configuration
comes from `agents/cursor-hooks.json` through `.cursor/hooks.json`.

| Hook | Script | Behavior |
|------|--------|----------|
| `sessionStart` | `koi-done-research-session.sh` | Adds an `additional_context` card list when the queue is non-empty |
| `stop` | `koi-done-research-stop.sh` | Sends a `followup_message` to process the next card while items remain (up to ten iterations) |

Inspect Cursor's **Hooks** output channel after opening a new Agent chat.

## Related skills

- Execute a card (TODO + kanban): **koi-execute-card**
- Review question/narrative style: **koi-prose-style**
- Reports: **koi-report-review**
- Development server: `koi-dev-server` (8010 + 8080)
- Visual review of conclusions: `koi-visual-qa`
- After saving a conclusion: **koi-project-sync** — commit and push `projects/`
