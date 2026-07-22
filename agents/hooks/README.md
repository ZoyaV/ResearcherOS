# Shared Cursor hooks

Hooks that are not owned by a single skill live here.

| Hook | Script | Role |
|------|--------|------|
| `sessionStart` | `koi-session-start.sh` | Start ResearchOS API (`scripts/koi-serve.sh`) if needed |

Skill-owned hooks live under `agents/skills/<skill>/hooks/`.

Wire them into the local IDE via `.cursor/hooks.json` (gitignored). Copy the
template:

```bash
cp agents/cursor-hooks.json .cursor/hooks.json
```
