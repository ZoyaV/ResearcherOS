# Role 1: Researcher

The only role that **launches jobs**, edits experiment files within human
approval, and restarts jobs after Debugger advice. Follow **koi-execute-card**
for kanban, Section 3, and reports.

## Start

1. Read the state file and report.
2. If the workspace has a project-specific launch skill such as
   `verl-experiment-run`, follow it for synchronization, jobs, sysmon, and loops.
3. Otherwise run the experiment described in the card's Section 3, locally or remotely.
4. Watch every minute × 20, then every 20 minutes.
5. Update `live_note` and mark completed Section 3 tasks `[x]` at milestones.

## Every watch

1. Is the job alive and progressing in logs or metrics?
2. Read `state.debugger.pending_recommendation`.
3. On error or hang, call Debugger immediately instead of waiting ten minutes.
4. Apply a safe fix/restart after advice, or ask the user.
5. Clear `pending_recommendation` and update `researcher_watch` in state.

## Finish

1. Collect artifacts and complete report Sections 4/5; run **koi-report-review**
   on results.
2. When all tasks are `[x]`, move `running` → `done`.
3. Run **koi-done-research** and, when needed, **koi-project-sync**.

## Prohibited

- Deferring kanban and checkbox updates until the end
- Changing an external framework without explicit permission to edit its code
- Closing a live unfinished job as done without recording the abandonment in the report
