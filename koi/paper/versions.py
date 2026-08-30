"""Git history for a paper's main.tex — working copy vs committed snapshots."""

from __future__ import annotations

import re
import subprocess
import time
from pathlib import Path
from typing import Any

_SHA = re.compile(r"^[0-9a-fA-F]{7,40}$")
_SLOT_COMMIT_NAMES = ("main.tex", "comments.json", "paper.json")


def _run_git(root: Path, *args: str, timeout: float = 8) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            ["git", *args],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return subprocess.CompletedProcess(["git", *args], 1, "", str(exc))


def _git_error(result: subprocess.CompletedProcess[str]) -> str:
    return (result.stderr or result.stdout or "git command failed").strip()


def _repo_root(tex_path: Path) -> Path:
    start = tex_path if tex_path.is_dir() else tex_path.parent
    result = _run_git(start, "rev-parse", "--show-toplevel")
    if result.returncode != 0 or not result.stdout.strip():
        return start
    return Path(result.stdout.strip())


def normalize_commit(sha: str) -> str:
    value = (sha or "").strip()
    if not _SHA.match(value):
        raise ValueError("Invalid version identifier")
    return value


def _relative_tex(tex_path: Path, repo: Path) -> str:
    try:
        return tex_path.resolve().relative_to(repo.resolve()).as_posix()
    except ValueError:
        return tex_path.name


def _parse_log(text: str) -> list[dict[str, Any]]:
    commits: list[dict[str, Any]] = []
    for line in text.splitlines():
        sha, _, rest = line.partition("\t")
        stamp, _, subject = rest.partition("\t")
        if not sha:
            continue
        try:
            committed_at = int(stamp)
        except ValueError:
            committed_at = 0
        commits.append(
            {
                "sha": sha,
                "short": sha[:8],
                "committed_at": committed_at,
                "subject": subject.strip() or sha[:8],
                "incoming": False,
            }
        )
    return commits


def _log_file(repo: Path, *rev_args: str, relative: str, limit: int) -> list[dict[str, Any]]:
    log = _run_git(
        repo,
        "log",
        "--follow",
        f"-n{limit}",
        "--format=%H\t%ct\t%s",
        *rev_args,
        "--",
        relative,
    )
    if log.returncode != 0:
        return []
    return _parse_log(log.stdout)


def _upstream_ref(repo: Path) -> str:
    tracked = _run_git(repo, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}")
    if tracked.returncode == 0 and tracked.stdout.strip():
        return tracked.stdout.strip()
    branch = _run_git(repo, "rev-parse", "--abbrev-ref", "HEAD")
    name = branch.stdout.strip()
    if name and name != "HEAD":
        return f"origin/{name}"
    return ""


_LAST_FETCH: dict[str, float] = {}


def _fetch_origin(repo: Path, *, force: bool = False, min_interval: float = 45) -> None:
    key = str(repo.resolve())
    now = time.monotonic()
    if not force and now - _LAST_FETCH.get(key, 0.0) < min_interval:
        return
    _LAST_FETCH[key] = now
    _run_git(repo, "fetch", "--quiet", "origin", timeout=20)


def list_paper_versions(project_id: str, tex_path: Path, *, limit: int = 40) -> dict[str, Any]:
    del project_id
    repo = _repo_root(tex_path)
    relative = _relative_tex(tex_path, repo)
    cap = max(1, min(int(limit), 80))
    _fetch_origin(repo)
    local = _log_file(repo, "HEAD", relative=relative, limit=cap)
    upstream = _upstream_ref(repo)
    incoming = _log_file(repo, f"HEAD..{upstream}", relative=relative, limit=cap) if upstream else []
    incoming_shas = {item["sha"] for item in incoming}
    for item in incoming:
        item["incoming"] = True
    commits = incoming + [item for item in local if item["sha"] not in incoming_shas]
    porcelain = _run_git(repo, "status", "--porcelain", "--", relative)
    comments = tex_path.with_name("comments.json")
    extra_dirty = False
    if comments.is_file():
        extra = _run_git(repo, "status", "--porcelain", "--", _relative_tex(comments, repo))
        extra_dirty = extra.returncode == 0 and bool(extra.stdout.strip())
    head = _run_git(repo, "rev-parse", "HEAD")
    return {
        "head": head.stdout.strip() if head.returncode == 0 else "",
        "dirty": (porcelain.returncode == 0 and bool(porcelain.stdout.strip())) or extra_dirty,
        "behind": len(incoming),
        "commits": commits,
    }


def pull_paper_versions(project_id: str, tex_path: Path) -> dict[str, Any]:
    repo = _repo_root(tex_path)
    _fetch_origin(repo, force=True)
    pulled = _run_git(repo, "pull", "--ff-only", "--quiet", timeout=30)
    if pulled.returncode != 0:
        fallback = _run_git(repo, "pull", "--quiet", timeout=30)
        if fallback.returncode != 0:
            raise RuntimeError(_git_error(fallback) or _git_error(pulled) or "Could not fetch updates")
    return list_paper_versions(project_id, tex_path)


def commit_and_push_paper(project_id: str, tex_path: Path, *, slug: str) -> dict[str, Any]:
    from koi.paper.collaboration.session import get_session

    session = get_session(project_id, slug)
    if session is not None and not session.closed:
        session.flush()
    repo = _repo_root(tex_path)
    slot = tex_path.parent
    to_add: list[str] = []
    for name in _SLOT_COMMIT_NAMES:
        path = slot / name
        if path.is_file():
            to_add.append(_relative_tex(path, repo))
    if to_add:
        added = _run_git(repo, "add", "--", *to_add)
        if added.returncode != 0:
            raise RuntimeError(_git_error(added) or "Could not add paper files")
    staged = _run_git(repo, "diff", "--cached", "--quiet")
    committed = False
    if staged.returncode == 1:
        message = f"Update {slug} paper"
        committed_run = _run_git(repo, "commit", "-m", message)
        if committed_run.returncode != 0:
            raise RuntimeError(_git_error(committed_run) or "Could not commit the paper")
        committed = True
    pushed = _run_git(repo, "push", "--quiet", "origin", "HEAD", timeout=30)
    if pushed.returncode != 0:
        raise RuntimeError(_git_error(pushed) or "Could not push the commit")
    versions = list_paper_versions(project_id, tex_path)
    return {"ok": True, "committed": committed, "pushed": True, **versions}


def paper_tex_at_commit(project_id: str, tex_path: Path, sha: str) -> str:
    del project_id
    commit = normalize_commit(sha)
    repo = _repo_root(tex_path)
    shown = _run_git(repo, "show", f"{commit}:{_relative_tex(tex_path, repo)}")
    if shown.returncode != 0:
        raise FileNotFoundError("This version has no main.tex")
    return shown.stdout
