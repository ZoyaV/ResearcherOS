# KOI program and laboratory format

An organizational layer **above** KOI projects. The hypothesis tree and kanban board remain in `projects/<id>/project.md`.

## Hierarchy

```
laboratory.md              — laboratory (mission and program order)
programs/<id>/program.md   — research program (list of project IDs)
projects/<id>/project.md   — KOI project (unchanged)
```

A project may belong to multiple programs. Membership is defined in `program.md` (`projects:`) and/or in project frontmatter (`programs:`).

## Laboratory (`laboratory.md`)

```yaml
---
id: zverl-koi
title: KOI Laboratory
description: Brief description
format: koi/laboratory/1
programs:
  - embodied-ai
  - isaac-harness
---
```

The `programs` field defines group order in the UI and global knowledge-base index.

## Program (`programs/<id>/program.md`)

```yaml
---
id: embodied-ai
title: Embodied AI agents
description: Brief program description
format: koi/program/1
projects:
  - ai-agents-embodied
---
```

The file body (Markdown after frontmatter) states the program's strategic question for humans and agents.

## Optional project fields

```yaml
---
id: my-project
title: ...
programs:
  - embodied-ai
---
```

## API

| Method | Path | Description |
|-------|------|----------|
| GET | `/laboratory` | Laboratory metadata |
| GET | `/programs` | Programs with project IDs |
| POST | `/programs` | Create a program (`title`, optional `description`) |
| GET | `/programs/{id}` | Program and project summary |
| GET | `/projects/grouped` | Projects grouped by program |
| GET | `/projects` | Project list; each item has a `programs` field |
| POST | `/projects` | Create a project; optional `program_id` adds it to a program immediately |

## KB

Aggregated program metrics are available through the laboratory API and ResearchOS interface.
