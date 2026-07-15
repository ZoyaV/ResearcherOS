---
name: koi-add-research-skill
description: >-
  Add or reorganize a ResearchOS skill with the repository's canonical harness
  layout. Use when creating a new skill for research workflows, deciding
  whether it belongs in agents/skills or .cursor/skills, exposing a research
  skill to Cursor, or reviewing skill placement and links.
---

# Add a ResearchOS skill

Keep one canonical implementation. Do not copy the same skill into multiple
agent-specific directories.

## Choose the owner

| Skill kind | Canonical location | Cursor exposure |
|---|---|---|
| Research/product workflow useful to a human researcher or any agent | `agents/skills/<name>/` | Optional symlink in `.cursor/skills/<name>` |
| ResearchOS development, refactoring, UI QA, repository maintenance | `.cursor/skills/<name>/` | Already Cursor-specific; do not duplicate in `agents/skills` |

If the workflow mixes both kinds, split it only when each part can be invoked
independently. Otherwise choose the owner matching its primary outcome.

## Workflow

1. Inspect `agents/skills/`, `.cursor/skills/`, `AGENTS.md`, and nearby skills.
   Extend an existing skill when the trigger and workflow substantially overlap.
2. Choose a lowercase hyphenated name, preferably prefixed with `koi-`.
3. Create exactly one canonical folder. Its `SKILL.md` frontmatter must contain
   only `name` and a trigger-oriented `description`.
4. Keep `SKILL.md` concise and imperative. Put reusable templates beside the
   owning skill; use `scripts/`, `references/`, or `assets/` only when needed.
5. For a research/product skill that Cursor must discover, create the link:

   ```bash
   python .cursor/skills/koi-add-research-skill/scripts/sync_cursor_link.py \
     <skill-name> --create
   ```

   Never create a second `SKILL.md` under `.cursor/skills/<name>`.
6. Add the skill to `AGENTS.md` only if agents need repository-wide routing or
   a mandatory workflow. Do not turn `AGENTS.md` into a duplicate of SKILL.md.
7. Update commands or documentation that should trigger the skill.
8. Validate before finishing:

   ```bash
   python .cursor/skills/koi-add-research-skill/scripts/sync_cursor_link.py \
     <skill-name> --check
   python /path/to/skill-creator/scripts/quick_validate.py \
     <canonical-skill-directory>
   git diff --check
   ```

   If `quick_validate.py` is unavailable, verify YAML frontmatter, folder/name
   equality, referenced resources, and every symlink manually.

## Required result

- One canonical skill implementation.
- No broken or absolute symlinks.
- No research template or helper left in a global miscellaneous directory.
- Trigger description states both what the skill does and when it applies.
- Relevant tests or a representative dry run pass.
