---
name: koi-project-sync
description: >-
  Auto-sync KOI projects/ with git: commit and push significant changes
  (completed experiments, reports, research questions, kanban); pull on Cursor
  startup and every 30 minutes. Use when the sync-push queue has items, after KOI
  workflows, on session start, or when the user mentions git sync, push, or pull.
---

# KOI: synchronize projects/ with git

The repository root is `KOI/` with remote `origin`. Project data lives only in
`projects/<id>/`.

## When to run

| Trigger | Action |
|---------|--------|
| `sessionStart` hook | **pull** |
| `stop` hook after at least 30 minutes | **pull** again |
| Non-empty push queue or dirty `projects/` | **commit + push** |
| After `koi-done-research`, saving a report, or moving a card to done | Check `pending-push` |
| User requests synchronization | Both directions |

At the start of a KOI session, **pull first, then process queues**
(done-research, agent-chat, push).

## CLI

```bash
KOI/.venv/bin/python -m koi.projects.sync_cli status
KOI/.venv/bin/python -m koi.projects.sync_cli pull
KOI/.venv/bin/python -m koi.projects.sync_cli pending-push
KOI/.venv/bin/python -m koi.projects.sync_cli complete-push --all
```

## Pull incoming changes

1. `pull` runs `git fetch` and `git pull --ff-only` when origin is ahead and
   `projects/` has no uncommitted files.
2. If local changes block an incoming pull, run the push workflow first, then
   pull. Report conflicts to the user and never force.
3. On the first session of the day, start a 30-minute background monitor with
   the `loop` skill if no loop exists:

```bash
# Loop every 30m: koi-project-sync pull
```

## Push outgoing changes

### Significant changes to commit

- a card moved to **done** or changed columns
- a new or updated **report** under `reports/`
- **research.json** / research_questions
- a new card, tree node, kanban change, or project.md edit

### Do not commit

- `.run/`, `.venv/`, `__pycache__/`
- KOI platform code (`koi/`, `api/`, `web/`) unless the user explicitly changed it
- secrets such as `.env`

### Workflow

1. Run `pending-push` to inspect `.run/sync-push-queue.json` and
   `git status projects/`.
2. If `needs_push`, group changes by project and stage only `projects/`:

```bash
cd KOI
git add projects/<project_id>/
git status
```

3. Use a concise English commit message:

```text
projects(<id>): <summary>

- <detail from the queue>
```

Examples:

- `projects(ai-agents-embodied): move Diversity-only experiment to done`
- `projects(isaaclab-dexsuite-reorient): add baseline PPO report`

4. Push only on an explicit skill or queue trigger; the user configured auto-sync:

```bash
cd KOI && git push origin HEAD
```

5. Run `complete-push --all` after a successful push.

### Rejected push (non-fast-forward)

Pull first, resolve conflicts under `projects/`, then push. Never use `--force`.

## Push queue

The API and agents add entries for significant changes. Fields are `project_id`,
`reason`, and `detail`. After processing done-research or a report, check push
immediately so conclusions reach the remote.

## Cursor hooks (ResearchOS workspace)

Scripts live in `agents/skills/koi-project-sync/hooks/`. Copy
`agents/cursor-hooks.json` to `.cursor/hooks.json` to enable them.

| Hook | Script | Behavior |
|------|--------|----------|
| `sessionStart` | `koi-project-sync-session.sh` | Pulls and adds context when push is pending or problems occur |
| `stop` | `koi-project-sync-stop.sh` | Requests a pull after 30 minutes and commit+push when the queue is non-empty |

## Related skills

- `koi-project-onboard` writes to `tree/<repo>/koi-structure/`, invokes
  `install_cli`, and performs the first push; ordinary synchronization continues here.
- `koi-done-research` — check push after saving a conclusion.
- `koi-dev-server` — the API writes to mounts and automatically fills the queue.
- `loop` — background pull every 30 minutes.

## Sibling repositories (`tree/<repo>/koi-structure` + orphan branch)

The canonical research-data working copy is `tree/<repo>/koi-structure/`, a git
worktree on `git_sync_branch` (usually `koi/research`). The code repository is
the sibling `<repo>/`.

If the layout does not yet use `tree/`:

```bash
python -m koi.projects.install_cli status
python -m koi.projects.install_cli install <repo>   # or migrate
```

For projects with `git_repo: true` and `git_sync_branch`, use:

```bash
python -m koi.projects.sync_cli init-sync-branch --project-id <id>
python -m koi.projects.sync_cli push --project-id <id>
python -m koi.projects.sync_cli pull --project-id <id>
python -m koi.projects.sync_cli status
```

Push and pull operate on the mounted `koi_root` under `tree/`; do not copy the
research tree back into the code branch.
