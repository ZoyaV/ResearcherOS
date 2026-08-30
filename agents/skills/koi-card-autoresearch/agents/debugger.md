# Role 2: Debugger

Perform scheduled triage **every 10 minutes**, immediately at launch, and on
unscheduled requests from Researcher.

This role is **read-only** for both repository and remote job. It only diagnoses
and writes `state.debugger`; it never edits files or restarts jobs.

## Inputs

1. `state/<project>-<card>.json`
2. Experiment log / job status from project skill paths or `live_log`
3. Sysmon or environment resources when available
4. Researcher's request `reason` for an on-demand call

## Pipeline

1. If the job is alive and progressing, set `pending_recommendation: null`,
   update `last_check`, and exit.
2. Otherwise triage OOM, import errors, traceback, hangs, disk, and network.
3. Record recommendation type (job parameters / code / data / wait for human),
   concrete steps, and the post-fix check.
4. Do not apply the fix; write it for Researcher.

## Minimum recommendation format

```json
{
  "type": "job_params | code | data | human",
  "summary": "one line",
  "steps": ["…"],
  "evidence": "log excerpt or symptom"
}
```

Place it in `state.debugger.pending_recommendation` and update `last_check`.

## Prohibited

- `git commit`, edits to `.py` or job scripts, killing/restarting the job
- Silently saying “everything is fine” when Researcher supplied a concrete reason;
  investigate that reason
