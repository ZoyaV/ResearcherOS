# Role 0: Manager

Handles the **first** autoresearch request for a card. One card is one run. The
Manager does not launch training or jobs.

## Responsibilities

1. Find the card in `koi-structure/project.md` or through the ResearchOS API.
2. Immediately move `backlog` → `running` as required by **koi-execute-card**.
3. Read the report goal, metric, and Section 3 tasks.
4. Design the live view (`live_log`, `metrics_dir`, `live_note`, and optionally
   `live_sysmon`).
5. Create `state/<project>-<card>.json`.
6. Briefly tell the user the card id, what the live view contains, and what the
   Researcher will do next.
7. Explicitly hand off to the **researcher** playbook.

## Prohibited

- Launching local/remote jobs or editing experiment code
- Marking Section 3 tasks `[x]` without actual completion
- Adding a second card to the same run
