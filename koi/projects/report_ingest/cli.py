#!/usr/bin/env python3
"""Agent-run hypothesis check: template report → automatic knowledge integration.

Run from the repository root:

    python -m koi.projects.report_ingest.cli <project_id> <card_id> \
        [--backend claude|cursor] [--no-ingest] [--dry-run] [--timeout 1800]
    python -m koi.projects.report_ingest.cli <project_id> <card_id> \
        --ingest-only [path/to/report.run.md]

Pipeline:
1. Resolve the node chain from the kanban card: method → evidence/remediation
   hypothesis → cause hypothesis → problem.
2. A local agent (Claude Code CLI or Cursor SDK; see
   koi/adapters/agent_backends.py) receives context and the
   `agents/skills/koi-report-review/experiment-report.md` template, then writes a
   `<card-report>.run.md` working report next to the public report.
3. `koi/projects/report_ingest/` parses the Knowledge base submission (Section 5):
   it assigns the verdict to the cause node, adds Section 5.2 JSON insights to
   research.json, and moves the card to done. The save_project hook then rebuilds
   KNOWLEDGE.md, knowledge/hypotheses.md, and KNOWLEDGE_LOG.md.

`--ingest-only` skips the agent and integrates an existing report. Pass an
explicit path or omit it to use the expected .run.md path.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from koi.adapters.agent_backends import backend_status, run_agent
from koi.core.models import NodeType, Project
from koi.projects.report_ingest import (
    ReportIngestError,
    expected_run_report_path,
    ingest_report,
)
from koi.adapters.repository import load_project
from koi.adapters.workspace import get_workspace

_ws = get_workspace()
TEMPLATE_PATH = _ws.experiment_report_template


def _find_card(project: Project, card_id: str):
    for board in project.boards:
        for card in board.cards:
            if card.id == card_id:
                return board, card
    return None, None


def _node_chain(project: Project, method_id: str) -> dict:
    """method → (cause_evidence|remediation) → cause → problem."""
    by_id = {n.id: n for n in project.nodes}
    chain: dict = {}
    node = by_id.get(method_id)
    while node is not None:
        chain[node.node_type.value] = node
        node = by_id.get(node.parent_id) if node.parent_id else None
    return chain


def _node_block(label: str, node) -> str:
    if node is None:
        return f"### {label}\n(none)\n"
    head = f"### {label}: `{node.id}` — {node.title}\n"
    body = (node.description or "").strip()
    extra = ""
    if node.node_type == NodeType.CAUSE:
        extra = f"\nCurrent verdict: {node.verdict.value}\n"
    return head + (body + "\n" if body else "") + extra


def build_prompt(project: Project, board, card, chain: dict, run_path: Path) -> str:
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    parent = chain.get("cause_evidence") or chain.get("remediation")
    ctx = "\n".join(
        [
            f"## Project: `{project.id}` — {project.title}",
            _node_block("Problem", chain.get("problem")),
            _node_block("Hypothesis (cause)", chain.get("cause")),
            _node_block("How it is tested", parent),
            _node_block("Method", chain.get("method")),
            f"### Experiment card: `{card.id}` — {card.title}",
            (card.description or "").strip(),
        ]
    )
    return f"""You are a ResearchOS experiment agent. Your task is to test the hypothesis from the experiment card and write a working report.

{ctx}

## Task

1. Run the check using the decision rule in the hypothesis description. If the
   method or card includes commands or existing raw metrics (logs, jsonl), use
   them. Run missing experiments only when the instructions explicitly require
   it. If there is no evidence to evaluate, say so plainly in the report and
   leave the verdict open.
2. Write the working report STRICTLY according to the template below:

   Report file: `{run_path}`

3. Hard requirements:
   - complete every section from 0 through 5 and remove all `>` hint lines;
   - Section 0 References: hypothesis `{(chain.get('cause').id if chain.get('cause') else '?')}`, method/card `{chain['method'].id}` / `{card.id}`;
   - in Section 3, derive the verdict by substituting measured values into the decision rule;
   - Section 5.2 must contain exactly one fenced ```json block: an array of at
     most three insights with fields
     method_id, card_id, question, answer, narrative, certainty
     (definite|tentative), and importance (1–5). Automatic integration requires it.
4. Change NOTHING except the report file. The pipeline updates project.md,
   research.json, and KNOWLEDGE.md automatically after your report.

## Report template (agents/skills/koi-report-review/experiment-report.md)

{template}
"""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("project_id")
    ap.add_argument("card_id")
    ap.add_argument("--backend", choices=["claude", "cursor"], default=None)
    ap.add_argument("--timeout", type=int, default=1800)
    ap.add_argument("--no-ingest", action="store_true",
                    help="generate the report without integrating it")
    ap.add_argument("--ingest-only", nargs="?", const="", metavar="REPORT",
                    default=None, help="skip the agent and integrate an existing report")
    ap.add_argument("--dry-run", action="store_true",
                    help="show integration changes without modifying files")
    args = ap.parse_args()

    project = load_project(args.project_id)
    if project is None:
        print(f"Project not found: {args.project_id}", file=sys.stderr)
        return 2
    board, card = _find_card(project, args.card_id)
    if card is None:
        print(f"Card not found: {args.card_id}", file=sys.stderr)
        return 2
    chain = _node_chain(project, board.owner_node_id)
    if "method" not in chain:
        print(f"Board {board.id} has no method node", file=sys.stderr)
        return 2

    run_path = expected_run_report_path(project, board.id, card.id, card.title)

    if args.ingest_only is None:
        prompt = build_prompt(project, board, card, chain, run_path)
        print(f"Backends: {json.dumps(backend_status(), ensure_ascii=False)}")
        print(f"Starting agent; waiting for report: {run_path}")
        text, backend = run_agent(
            prompt, cwd=_ws.agent_cwd(), timeout=args.timeout,
            allow_edits=True, backend=args.backend,
        )
        if text is None:
            print(
                "No agent backend is available or returned a response. "
                "Use Claude Code CLI (claude login / ANTHROPIC_API_KEY) "
                "or CURSOR_API_KEY + cursor_sdk.",
                file=sys.stderr,
            )
            return 3
        print(f"Agent ({backend}) finished.")
        if not run_path.is_file() or not run_path.read_text(encoding="utf-8").strip():
            print(f"The agent did not write the report: {run_path}", file=sys.stderr)
            print(f"Final agent message:\n{text}", file=sys.stderr)
            return 4
        if args.no_ingest:
            print(f"Report ready (integration skipped): {run_path}")
            return 0
    else:
        run_path = Path(args.ingest_only) if args.ingest_only else run_path
        if not args.ingest_only and (
            not run_path.is_file() or not run_path.read_text(encoding="utf-8").strip()
        ):
            # If the working .run.md is absent, try the public UI card report.
            public = run_path.with_name(run_path.name.replace(".run.md", ".md"))
            if public.is_file() and public.read_text(encoding="utf-8").strip():
                print(f"Working .run.md not found; integrating UI report: {public}")
                run_path = public

    try:
        summary = ingest_report(args.project_id, run_path, dry_run=args.dry_run)
    except ReportIngestError as e:
        print(f"Automatic integration failed: {e}", file=sys.stderr)
        return 5
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
