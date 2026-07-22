"""Persistence for users, projects, sessions, and snapshots."""

from __future__ import annotations

import json
import mimetypes
import secrets
import shutil
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from hub.app.config import HubConfig


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class HubUser:
    github_id: int
    login: str
    avatar_url: str = ""
    discoverable: bool = True
    created_at: str = field(default_factory=_utcnow)


@dataclass
class HubProject:
    slug: str
    owner_github_id: int
    owner_login: str
    repo_full_name: str
    branch: str
    title: str
    visibility: str  # public | network | unlisted
    secret_token: str = ""
    composite_id: str = ""
    programs: list[dict[str, str]] = field(default_factory=list)
    enabled: bool = True
    last_sync_at: str = ""
    last_commit: str = ""
    created_at: str = field(default_factory=_utcnow)


def parse_hub_project(raw: dict) -> HubProject:
    data = dict(raw)
    data.setdefault("enabled", True)
    data.setdefault("composite_id", "")
    data.setdefault("programs", [])
    programs = data.get("programs") or []
    if not isinstance(programs, list):
        programs = []
    normalized: list[dict[str, str]] = []
    for item in programs:
        if isinstance(item, dict):
            pid = str(item.get("id") or "").strip()
            if not pid:
                continue
            normalized.append(
                {
                    "id": pid,
                    "title": str(item.get("title") or pid),
                    "description": str(item.get("description") or ""),
                }
            )
        elif item:
            pid = str(item).strip()
            if pid:
                normalized.append({"id": pid, "title": pid, "description": ""})
    data["programs"] = normalized
    return HubProject(**data)


@dataclass
class HubSession:
    session_id: str
    github_id: int
    access_token: str
    created_at: str = field(default_factory=_utcnow)


class HubStore:
    def __init__(self, config: HubConfig) -> None:
        self.config = config
        self._s3 = None
        if config.use_s3:
            import boto3

            self._s3 = boto3.client(
                "s3",
                endpoint_url=config.s3_endpoint,
                aws_access_key_id=config.s3_access_key,
                aws_secret_access_key=config.s3_secret_key,
            )
        else:
            config.data_dir.mkdir(parents=True, exist_ok=True)

    def _key(self, *parts: str) -> str:
        return "/".join(parts)

    def _read_json(self, key: str) -> Any:
        if self._s3:
            try:
                obj = self._s3.get_object(Bucket=self.config.s3_bucket, Key=key)
                return json.loads(obj["Body"].read().decode("utf-8"))
            except Exception as exc:
                code = getattr(getattr(exc, "response", None), "get", lambda *_: {})("Error", {}).get("Code")
                if code in {"NoSuchKey", "404"}:
                    return None
                return None
        path = self.config.data_dir / key
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def _write_json(self, key: str, data: Any) -> None:
        body = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
        if self._s3:
            self._s3.put_object(
                Bucket=self.config.s3_bucket,
                Key=key,
                Body=body.encode("utf-8"),
                ContentType="application/json",
            )
            return
        path = self.config.data_dir / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")

    def list_users(self) -> list[HubUser]:
        index = self._read_json("users/index.json") or []
        users: list[HubUser] = []
        for github_id in index:
            raw = self._read_json(f"users/{github_id}.json")
            if raw:
                users.append(HubUser(**raw))
        return users

    def get_user(self, github_id: int) -> Optional[HubUser]:
        raw = self._read_json(f"users/{github_id}.json")
        return HubUser(**raw) if raw else None

    def save_user(self, user: HubUser) -> None:
        self._write_json(f"users/{user.github_id}.json", asdict(user))
        index = self._read_json("users/index.json") or []
        sid = str(user.github_id)
        if sid not in index:
            index.append(sid)
            self._write_json("users/index.json", index)

    def list_projects(self) -> list[HubProject]:
        index = self._read_json("projects/index.json") or []
        out: list[HubProject] = []
        for slug in index:
            raw = self._read_json(f"projects/{slug}.json")
            if raw:
                out.append(parse_hub_project(raw))
        return out

    def get_project(self, slug: str) -> Optional[HubProject]:
        raw = self._read_json(f"projects/{slug}.json")
        return parse_hub_project(raw) if raw else None

    def save_project(self, project: HubProject) -> None:
        self._write_json(f"projects/{project.slug}.json", asdict(project))
        index = self._read_json("projects/index.json") or []
        if project.slug not in index:
            index.append(project.slug)
            self._write_json("projects/index.json", index)

    def delete_project(self, slug: str) -> None:
        if self._s3:
            self._s3.delete_object(Bucket=self.config.s3_bucket, Key=f"projects/{slug}.json")
            self._s3.delete_object(Bucket=self.config.s3_bucket, Key=f"snapshots/{slug}.json")
            self._delete_prefix(f"reports/{slug}/")
            self._delete_prefix(f"skills/entries/{slug}/")
        else:
            project_path = self.config.data_dir / "projects" / f"{slug}.json"
            snapshot_path = self.config.data_dir / "snapshots" / f"{slug}.json"
            reports_path = self.reports_dir(slug)
            skills_path = self.config.data_dir / "skills" / "entries" / slug
            if project_path.exists():
                project_path.unlink()
            if snapshot_path.exists():
                snapshot_path.unlink()
            if reports_path.exists():
                shutil.rmtree(reports_path, ignore_errors=True)
            if skills_path.exists():
                shutil.rmtree(skills_path, ignore_errors=True)
        index = self._read_json("projects/index.json") or []
        if slug in index:
            index = [s for s in index if s != slug]
            self._write_json("projects/index.json", index)
        self.clear_project_skills(slug)

    def save_snapshot(self, slug: str, payload: dict[str, Any]) -> None:
        self._write_json(f"snapshots/{slug}.json", payload)

    def get_snapshot(self, slug: str) -> Optional[dict[str, Any]]:
        return self._read_json(f"snapshots/{slug}.json")

    # --- Public skills pool (git SoT → snapshot on sync) ---

    def _skill_entry_key(self, project_slug: str, skill_id: str) -> str:
        return f"skills/entries/{project_slug}/{skill_id}.json"

    def get_skill(self, project_slug: str, skill_id: str) -> Optional[dict[str, Any]]:
        return self._read_json(self._skill_entry_key(project_slug, skill_id))

    def list_skills_catalog(self) -> list[dict[str, Any]]:
        rows = self._read_json("skills/index.json") or []
        return rows if isinstance(rows, list) else []

    def clear_project_skills(self, project_slug: str) -> None:
        """Remove all skills published from a project and refresh the catalog."""
        if self._s3:
            self._delete_prefix(f"skills/entries/{project_slug}/")
        else:
            path = self.config.data_dir / "skills" / "entries" / project_slug
            if path.exists():
                shutil.rmtree(path, ignore_errors=True)
        self._write_json(f"skills/by-project/{project_slug}.json", [])
        self._rebuild_skills_index()

    def replace_project_skills(
        self, project_slug: str, entries: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Replace the skill set for one project, then rebuild the global catalog."""
        prev_ids = self._read_json(f"skills/by-project/{project_slug}.json") or []
        if not isinstance(prev_ids, list):
            prev_ids = []
        new_ids = [str(e["id"]) for e in entries if e.get("id")]
        removed = [sid for sid in prev_ids if sid not in new_ids]
        for skill_id in removed:
            self._delete_skill_entry(project_slug, skill_id)
        for entry in entries:
            skill_id = str(entry.get("id") or "").strip()
            if not skill_id:
                continue
            self._write_json(self._skill_entry_key(project_slug, skill_id), entry)
        self._write_json(f"skills/by-project/{project_slug}.json", new_ids)
        self._rebuild_skills_index()
        return new_ids

    def _delete_skill_entry(self, project_slug: str, skill_id: str) -> None:
        key = self._skill_entry_key(project_slug, skill_id)
        if self._s3:
            try:
                self._s3.delete_object(Bucket=self.config.s3_bucket, Key=key)
            except Exception:
                pass
            return
        path = self.config.data_dir / key
        if path.exists():
            path.unlink()

    def _rebuild_skills_index(self) -> None:
        """Rebuild ``skills/index.json`` from all by-project id lists."""
        by_project_index = self._read_json("skills/by-project/index.json")
        # Discover project slugs that have skill lists.
        project_slugs: list[str] = []
        if self._s3:
            prefix = "skills/by-project/"
            token = None
            while True:
                kwargs: dict[str, Any] = {
                    "Bucket": self.config.s3_bucket,
                    "Prefix": prefix,
                }
                if token:
                    kwargs["ContinuationToken"] = token
                resp = self._s3.list_objects_v2(**kwargs)
                for item in resp.get("Contents") or []:
                    key = str(item.get("Key") or "")
                    name = key[len(prefix) :]
                    if name.endswith(".json") and name != "index.json":
                        project_slugs.append(name[: -len(".json")])
                if not resp.get("IsTruncated"):
                    break
                token = resp.get("NextContinuationToken")
        else:
            root = self.config.data_dir / "skills" / "by-project"
            if root.is_dir():
                for path in root.glob("*.json"):
                    if path.name == "index.json":
                        continue
                    project_slugs.append(path.stem)

        # Keep discovery list for debugging; not required for reads.
        if by_project_index is None or set(by_project_index or []) != set(project_slugs):
            self._write_json("skills/by-project/index.json", sorted(set(project_slugs)))

        catalog: list[dict[str, Any]] = []
        for slug in sorted(set(project_slugs)):
            ids = self._read_json(f"skills/by-project/{slug}.json") or []
            if not isinstance(ids, list):
                continue
            for skill_id in ids:
                entry = self.get_skill(slug, str(skill_id))
                if not entry:
                    continue
                catalog.append(
                    {
                        "key": entry.get("key") or f"{slug}/{skill_id}",
                        "id": entry.get("id") or skill_id,
                        "title": entry.get("title") or skill_id,
                        "summary": entry.get("summary") or "",
                        "project_slug": entry.get("project_slug") or slug,
                        "project_title": entry.get("project_title") or "",
                        "owner_login": entry.get("owner_login") or "",
                        "repo_full_name": entry.get("repo_full_name") or "",
                        "synced_at": entry.get("synced_at") or "",
                        "has_skill_md": bool(entry.get("has_skill_md")),
                        "files_count": len(entry.get("files") or []),
                        "view_url": entry.get("view_url")
                        or f"/skills/{slug}/{skill_id}",
                        "download_url": entry.get("download_url")
                        or f"/api/skills/{slug}/{skill_id}/download",
                        "project_url": entry.get("project_url") or f"/p/{slug}",
                    }
                )
        catalog.sort(
            key=lambda row: (row.get("synced_at") or "", row.get("title") or ""),
            reverse=True,
        )
        self._write_json("skills/index.json", catalog)

    def reports_dir(self, slug: str) -> Path:
        return self.config.data_dir / "reports" / slug

    def save_reports_tree(self, slug: str, src: Path) -> int:
        """Copy ``koi-structure/reports`` into Hub storage. Returns file count.

        Uploads first, then prunes removed keys. Never wipe-then-upload: a
        timeout mid-sync would leave the Hub with an empty/partial reports tree.
        """
        if not src.is_dir():
            self._clear_reports(slug)
            return 0
        if self._s3:
            prefix = f"reports/{slug}/"
            keep: set[str] = set()
            count = 0
            for path in src.rglob("*"):
                if not path.is_file():
                    continue
                rel = path.relative_to(src).as_posix()
                key = f"{prefix}{rel}"
                body = path.read_bytes()
                content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
                self._s3.put_object(
                    Bucket=self.config.s3_bucket,
                    Key=key,
                    Body=body,
                    ContentType=content_type,
                )
                keep.add(key)
                count += 1
            # Drop orphans from previous syncs (paginated).
            token = None
            while True:
                kwargs: dict[str, Any] = {
                    "Bucket": self.config.s3_bucket,
                    "Prefix": prefix,
                }
                if token:
                    kwargs["ContinuationToken"] = token
                resp = self._s3.list_objects_v2(**kwargs)
                stale = [
                    {"Key": item["Key"]}
                    for item in resp.get("Contents") or []
                    if item.get("Key") and item["Key"] not in keep
                ]
                if stale:
                    # delete_objects accepts ≤1000 keys per call
                    for i in range(0, len(stale), 1000):
                        self._s3.delete_objects(
                            Bucket=self.config.s3_bucket,
                            Delete={"Objects": stale[i : i + 1000]},
                        )
                if not resp.get("IsTruncated"):
                    break
                token = resp.get("NextContinuationToken")
            return count

        dest = self.reports_dir(slug)
        if dest.exists():
            shutil.rmtree(dest, ignore_errors=True)
        shutil.copytree(src, dest)
        return sum(1 for p in dest.rglob("*") if p.is_file())

    def resolve_report_file(self, slug: str, relative: str) -> Optional[Path]:
        """Resolve a path under stored reports/; materializes from S3 when needed."""
        rel = relative.strip().lstrip("/")
        if not rel or ".." in Path(rel).parts:
            return None
        if self._s3:
            key = f"reports/{slug}/{rel}"
            cache = self.config.data_dir / ".s3-cache" / "reports" / slug / rel
            try:
                obj = self._s3.get_object(Bucket=self.config.s3_bucket, Key=key)
                cache.parent.mkdir(parents=True, exist_ok=True)
                cache.write_bytes(obj["Body"].read())
                return cache
            except Exception:
                return None
        path = (self.reports_dir(slug) / rel).resolve()
        root = self.reports_dir(slug).resolve()
        if not str(path).startswith(str(root) + "/") and path != root:
            return None
        return path if path.is_file() else None

    def _clear_reports(self, slug: str) -> None:
        if self._s3:
            self._delete_prefix(f"reports/{slug}/")
            return
        dest = self.reports_dir(slug)
        if dest.exists():
            shutil.rmtree(dest, ignore_errors=True)

    def _delete_prefix(self, prefix: str) -> None:
        if not self._s3:
            return
        token = None
        while True:
            kwargs: dict[str, Any] = {
                "Bucket": self.config.s3_bucket,
                "Prefix": prefix,
            }
            if token:
                kwargs["ContinuationToken"] = token
            resp = self._s3.list_objects_v2(**kwargs)
            objs = [{"Key": item["Key"]} for item in resp.get("Contents") or []]
            if objs:
                self._s3.delete_objects(
                    Bucket=self.config.s3_bucket,
                    Delete={"Objects": objs},
                )
            if not resp.get("IsTruncated"):
                break
            token = resp.get("NextContinuationToken")

    def create_session(self, github_id: int, access_token: str) -> HubSession:
        session = HubSession(
            session_id=secrets.token_urlsafe(32),
            github_id=github_id,
            access_token=access_token,
        )
        self._write_json(f"sessions/{session.session_id}.json", asdict(session))
        return session

    def get_session(self, session_id: str) -> Optional[HubSession]:
        raw = self._read_json(f"sessions/{session_id}.json")
        return HubSession(**raw) if raw else None

    def delete_session(self, session_id: str) -> None:
        if self._s3:
            self._s3.delete_object(
                Bucket=self.config.s3_bucket,
                Key=self._key("sessions", f"{session_id}.json"),
            )
            return
        path = self.config.data_dir / "sessions" / f"{session_id}.json"
        if path.exists():
            path.unlink()

    def list_follows(self) -> list[dict[str, int]]:
        return self._read_json("social/follows.json") or []

    def add_follow(self, follower_id: int, following_id: int) -> None:
        rows = self.list_follows()
        if any(r["follower_id"] == follower_id and r["following_id"] == following_id for r in rows):
            return
        rows.append({"follower_id": follower_id, "following_id": following_id})
        self._write_json("social/follows.json", rows)

    def following_ids(self, follower_id: int) -> set[int]:
        return {r["following_id"] for r in self.list_follows() if r["follower_id"] == follower_id}

    def list_bookmarks(self) -> list[dict[str, Any]]:
        return self._read_json("social/bookmarks.json") or []

    def user_bookmarks(self, user_id: int) -> list[dict[str, str]]:
        return [
            {"slug": str(r["slug"]), "token": str(r.get("token") or "")}
            for r in self.list_bookmarks()
            if r.get("user_id") == user_id
        ]

    def add_bookmark(self, user_id: int, slug: str, token: str = "") -> bool:
        rows = self.list_bookmarks()
        for row in rows:
            if row.get("user_id") == user_id and row.get("slug") == slug:
                if token and row.get("token") != token:
                    row["token"] = token
                    self._write_json("social/bookmarks.json", rows)
                return False
        rows.append(
            {
                "user_id": user_id,
                "slug": slug,
                "token": token or "",
                "created_at": _utcnow(),
            }
        )
        self._write_json("social/bookmarks.json", rows)
        return True

    def remove_bookmark(self, user_id: int, slug: str) -> None:
        rows = [
            r
            for r in self.list_bookmarks()
            if not (r.get("user_id") == user_id and r.get("slug") == slug)
        ]
        self._write_json("social/bookmarks.json", rows)

    def _likes_key(self, slug: str) -> str:
        return f"social/likes/{slug}.json"

    def get_likes(self, slug: str) -> dict[str, Any]:
        raw = self._read_json(self._likes_key(slug)) or {}
        user_ids: list[int] = []
        for item in raw.get("user_ids") or []:
            try:
                user_ids.append(int(item))
            except (TypeError, ValueError):
                continue
        # Preserve order, drop duplicates.
        seen: set[int] = set()
        ordered: list[int] = []
        for uid in user_ids:
            if uid in seen:
                continue
            seen.add(uid)
            ordered.append(uid)
        return {
            "user_ids": ordered,
            "updated_at": str(raw.get("updated_at") or ""),
            "count": len(ordered),
        }

    def toggle_like(self, user_id: int, slug: str) -> dict[str, Any]:
        data = self.get_likes(slug)
        user_ids = list(data["user_ids"])
        if user_id in user_ids:
            user_ids = [uid for uid in user_ids if uid != user_id]
            liked = False
        else:
            user_ids.append(user_id)
            liked = True
        payload = {"user_ids": user_ids, "updated_at": _utcnow()}
        self._write_json(self._likes_key(slug), payload)
        return {"liked": liked, "count": len(user_ids)}

    @staticmethod
    def new_slug(title: str, repo_full_name: str) -> str:
        base = title.lower().strip() or repo_full_name.split("/")[-1]
        cleaned = "".join(ch if ch.isalnum() else "-" for ch in base).strip("-")
        cleaned = "-".join(part for part in cleaned.split("-") if part)[:40] or "project"
        suffix = uuid.uuid4().hex[:6]
        return f"{cleaned}-{suffix}"

    @staticmethod
    def new_secret() -> str:
        return secrets.token_urlsafe(18)
