#!/usr/bin/env python3
"""Git sync helpers for KOI projects/ — pull remote, queue and commit significant changes."""

from __future__ import annotations

import argparse
import json

from koi.adapters.project_sync import (
    git_summary,
    init_sync_branches,
    push_projects,
)
from koi.projects.sync import pull_projects
from koi.adapters.project_sync_queue import (
    clear_push_queue,
    dequeue_push,
    enqueue_push,
    list_pending_push,
    should_periodic_pull,
)
from koi.adapters.project_mount import list_mounts


def cmd_status() -> None:
    print(json.dumps(git_summary(), ensure_ascii=False, indent=2))


def cmd_pull(args: argparse.Namespace) -> None:
    result = pull_projects(dry_run=args.dry_run, project_id=args.project_id)
    print(json.dumps(result, ensure_ascii=False, indent=2))


def cmd_push(args: argparse.Namespace) -> None:
    result = push_projects(
        dry_run=args.dry_run,
        project_id=args.project_id,
        message=args.message,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


def cmd_init_sync(args: argparse.Namespace) -> None:
    result = init_sync_branches(
        dry_run=args.dry_run,
        project_id=args.project_id,
        push=not args.no_push,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


def cmd_pending_push() -> None:
    summary = git_summary()
    print(
        json.dumps(
            {
                "pending_push": summary.get("pending_push", []),
                "dirty_project_paths": summary.get("dirty_project_paths", []),
                "needs_push": bool(summary.get("pending_push"))
                or bool(summary.get("dirty_project_paths")),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def cmd_enqueue(args: argparse.Namespace) -> None:
    enqueue_push(args.project_id, args.reason, args.detail)
    print(json.dumps({"enqueued": True}, ensure_ascii=False))


def cmd_complete_push(args: argparse.Namespace) -> None:
    if args.all:
        removed = len(list_pending_push())
        clear_push_queue()
    else:
        removed = dequeue_push(args.project_id)
    print(json.dumps({"removed": removed}, ensure_ascii=False))


def cmd_should_pull() -> None:
    print(json.dumps({"should_pull": should_periodic_pull()}, ensure_ascii=False))


def cmd_list_projects() -> None:
    ids = sorted(m.project_id for m in list_mounts())
    print(json.dumps(ids, ensure_ascii=False))


def main() -> None:
    parser = argparse.ArgumentParser(description="KOI project git sync")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("status", help="Git status focused on projects/")
    p_pull = sub.add_parser("pull", help="Fetch and update koi-structure from sync branch")
    p_pull.add_argument("--dry-run", action="store_true")
    p_pull.add_argument("--project-id", dest="project_id", default=None)

    p_push = sub.add_parser("push", help="Commit and push koi-structure to sync branch")
    p_push.add_argument("--dry-run", action="store_true")
    p_push.add_argument("--project-id", dest="project_id", default=None)
    p_push.add_argument("--message", default=None)

    p_init = sub.add_parser("init-sync-branch", help="Create orphan koi sync branch if missing")
    p_init.add_argument("--dry-run", action="store_true")
    p_init.add_argument("--project-id", dest="project_id", default=None)
    p_init.add_argument("--no-push", action="store_true")

    sub.add_parser("pending-push", help="Push queue + dirty project files")
    sub.add_parser("should-pull", help="True if periodic pull is due (30 min)")
    sub.add_parser("list-projects", help="List project ids")

    p_enq = sub.add_parser("enqueue", help="Enqueue significant change for push")
    p_enq.add_argument("project_id")
    p_enq.add_argument("reason")
    p_enq.add_argument("detail")

    p_done = sub.add_parser("complete-push", help="Clear push queue after successful push")
    p_done.add_argument("--all", action="store_true")
    p_done.add_argument("--project-id", dest="project_id", default=None)

    args = parser.parse_args()
    handlers = {
        "status": lambda a: cmd_status(),
        "pull": cmd_pull,
        "push": cmd_push,
        "init-sync-branch": cmd_init_sync,
        "pending-push": lambda a: cmd_pending_push(),
        "should-pull": lambda a: cmd_should_pull(),
        "list-projects": lambda a: cmd_list_projects(),
        "enqueue": cmd_enqueue,
        "complete-push": cmd_complete_push,
    }
    handlers[args.cmd](args)


if __name__ == "__main__":
    main()
