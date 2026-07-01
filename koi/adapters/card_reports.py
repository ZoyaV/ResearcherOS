"""Markdown reports for kanban cards: koi-structure/reports/<method>/<card>.md"""

from __future__ import annotations

import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import uuid4

from koi.core.models import NodeType
from koi.adapters.paths import reports_dir as project_reports_dir
from koi.adapters.workspace import get_workspace

if TYPE_CHECKING:
    from koi.core.models import Project

INDEX_NAME = "index.json"
RUN_EXT = ".run.md"
TEMPLATE_PATH = get_workspace().experiment_report_template
MAX_BASENAME = 120
ASSETS_DIR = "assets"
MAX_ASSET_BYTES = 10 * 1024 * 1024

MIME_TO_EXT = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/gif": ".gif",
    "image/webp": ".webp",
}


def reports_dir(project_id: str) -> Path:
    d = project_reports_dir(project_id)
    d.mkdir(parents=True, exist_ok=True)
    return d


def _index_path(project_id: str) -> Path:
    return reports_dir(project_id) / INDEX_NAME


def slugify_name(title: str) -> str:
    """Spaces → underscores; strip unsafe path characters."""
    s = title.strip()
    s = re.sub(r"\s+", "_", s)
    s = re.sub(r'[<>"/\\|?*\x00-\x1f]', "", s)
    s = s.strip() or "report"
    if len(s) > MAX_BASENAME:
        s = s[:MAX_BASENAME].rstrip("._")
    return s or "report"


def card_report_basename(title: str) -> str:
    return slugify_name(title)


def owner_slug_for_board(project: Project, board_id: str) -> str:
    board = next(b for b in project.boards if b.id == board_id)
    node = next(n for n in project.nodes if n.id == board.owner_node_id)
    return slugify_name(node.title)


def load_index(project_id: str) -> dict[str, str]:
    path = _index_path(project_id)
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return {k: v for k, v in data.items() if isinstance(k, str) and isinstance(v, str)}
    except (json.JSONDecodeError, OSError):
        return {}


def save_index(project_id: str, index: dict[str, str]) -> None:
    path = _index_path(project_id)
    path.write_text(
        json.dumps(index, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _unique_card_filename(used_in_folder: set[str], title: str) -> str:
    base = card_report_basename(title)
    candidate = f"{base}.md"
    if candidate not in used_in_folder:
        return candidate
    n = 2
    while True:
        candidate = f"{base}_{n}.md"
        if candidate not in used_in_folder:
            return candidate
        n += 1


def _expected_relative(
    project: Project,
    board_id: str,
    card_id: str,
    card_title: str,
    index: dict[str, str],
) -> str:
    """Compute canonical relative path owner_slug/card.md (in-memory index)."""
    owner_slug = owner_slug_for_board(project, board_id)
    if card_id in index:
        rel = index[card_id]
        if "/" in rel and rel.split("/")[0] == owner_slug:
            return rel
    used = {
        Path(v).name
        for cid, v in index.items()
        if cid != card_id and v.startswith(f"{owner_slug}/")
    }
    filename = _unique_card_filename(used, card_title)
    return f"{owner_slug}/{filename}"


def report_path_for_relative(project_id: str, relative: str) -> Path:
    return reports_dir(project_id) / relative


def _migrate_flat_entry(
    project_id: str,
    card_id: str,
    old_rel: str,
    new_rel: str,
    index: dict[str, str],
) -> None:
    root = reports_dir(project_id)
    old_path = root / old_rel
    new_path = report_path_for_relative(project_id, new_rel)
    new_path.parent.mkdir(parents=True, exist_ok=True)
    if old_path.exists() and old_path != new_path:
        if new_path.exists():
            new_path.write_text(
                new_path.read_text(encoding="utf-8")
                + old_path.read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            old_path.unlink()
        else:
            shutil.move(str(old_path), str(new_path))
    elif not new_path.exists():
        new_path.write_text("", encoding="utf-8")
    index[card_id] = new_rel


def ensure_card_report(
    project: Project, board_id: str, card_id: str, card_title: str
) -> Path:
    """Create report file + index entry if missing (single index read/write)."""
    project_id = project.id
    index = load_index(project_id)
    relative = _expected_relative(project, board_id, card_id, card_title, index)
    if index.get(card_id) != relative:
        index[card_id] = relative
        save_index(project_id, index)
    path = report_path_for_relative(project_id, relative)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text("", encoding="utf-8")
    return path


def sync_reports_for_project(project: Project) -> int:
    """Ensure reports under reports/<hypothesis>/; migrate legacy flat files."""
    project_id = project.id
    card_ids = {c.id for b in project.boards for c in b.cards}
    index = load_index(project_id)
    index_dirty = False
    created = 0

    for cid in list(index.keys()):
        if cid not in card_ids:
            rel = index.pop(cid)
            path = report_path_for_relative(project_id, rel)
            if path.exists():
                path.unlink()
            index_dirty = True

    for board in project.boards:
        owner_slug = owner_slug_for_board(project, board.id)
        (reports_dir(project_id) / owner_slug).mkdir(parents=True, exist_ok=True)

        for card in board.cards:
            new_rel = _expected_relative(
                project, board.id, card.id, card.title, index
            )
            old_rel = index.get(card.id)

            if old_rel and old_rel != new_rel:
                _migrate_flat_entry(project_id, card.id, old_rel, new_rel, index)
                index_dirty = True
            elif old_rel is None:
                index[card.id] = new_rel
                index_dirty = True

            path = report_path_for_relative(project_id, new_rel)
            if not path.exists():
                path.write_text("", encoding="utf-8")
                created += 1

    if index_dirty:
        save_index(project_id, index)
    return created


def _report_meta(project_id: str, card_id: str, relative: str, path: Path) -> dict[str, str]:
    return {
        "content": path.read_text(encoding="utf-8") if path.exists() else "",
        "filename": path.name,
        "relative_path": f"reports/{relative}",
        "hypothesis_dir": relative.split("/")[0] if "/" in relative else "",
    }


def report_path_info(
    project: Project, board_id: str, card_id: str, card_title: str
) -> dict[str, str]:
    """Paths to the card report file (no file read/create)."""
    from koi.adapters.paths import repo_root

    project_id = project.id
    index = load_index(project_id)
    relative = _expected_relative(project, board_id, card_id, card_title, index)
    relative_path = f"reports/{relative}"
    koi_path = f"koi-structure/{relative_path}"
    repo_path = f"{repo_root(project_id).name}/{koi_path}"
    return {
        "card_id": card_id,
        "relative_path": relative_path,
        "koi_path": koi_path,
        "repo_path": repo_path,
    }


def _board_chain(project: Project, board_id: str):
    """(cause, method) для доски: владелец — метод, причина — вверх по дереву."""
    board = next((b for b in project.boards if b.id == board_id), None)
    if board is None:
        return None, None
    by_id = {n.id: n for n in project.nodes}
    method = by_id.get(board.owner_node_id)
    cause, cur = None, method
    while cur is not None:
        if cur.node_type == NodeType.CAUSE:
            cause = cur
            break
        cur = by_id.get(cur.parent_id) if cur.parent_id else None
    return cause, method


def report_scaffold(project: Project, board_id: str, card_id: str, card_title: str) -> str:
    """Шаблон отчёта с уже подставленной привязкой (§0, §5.1, §5.2)."""
    cause, method = _board_chain(project, board_id)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    try:
        text = TEMPLATE_PATH.read_text(encoding="utf-8")
    except OSError:
        cause_id = cause.id if cause else "<id-причины>"
        method_id = method.id if method else "<id-метода>"
        return (
            f"# Отчёт: {card_title}\n\n## 0. Привязка\n\n"
            "| Поле | Значение |\n|------|----------|\n"
            f"| Гипотеза (cause) | `{cause_id}` |\n"
            f"| Метод / карточка | `{method_id}` / `{card_id}` |\n"
            f"| Дата прогона | {today} |\n"
        )
    text = text.replace(
        "# Отчёт о прогоне эксперимента (рабочий)", f"# Отчёт: {card_title}", 1
    )
    if cause is not None:
        text = text.replace("`c-…` — короткое имя", f"`{cause.id}` — {cause.title}", 1)
        text = text.replace("- `c-…` →", f"- `{cause.id}` →", 1)
    if method is not None:
        text = text.replace("`m-…` / `…`", f"`{method.id}` / `{card_id}`", 1)
        text = text.replace('"method_id": "m-…"', f'"method_id": "{method.id}"', 1)
        text = text.replace('"card_id": "…"', f'"card_id": "{card_id}"', 1)
    text = text.replace("| YYYY-MM-DD |", f"| {today} |", 1)
    return text


def read_report_indexed(project_id: str, card_id: str) -> dict[str, str] | None:
    """Read a saved report from ``index.json`` without a kanban card (legacy/orphan ids)."""
    index = load_index(project_id)
    rel = index.get(card_id)
    if not rel:
        return None
    path = report_path_for_relative(project_id, rel)
    if not path.is_file():
        return None
    meta = _report_meta(project_id, card_id, rel, path)
    if meta["content"].strip():
        meta["source"] = "saved"
        return meta
    return None


def read_report(project: Project, board_id: str, card_id: str, card_title: str) -> dict[str, str]:
    project_id = project.id
    index = load_index(project_id)
    if card_id in index and report_path_for_relative(project_id, index[card_id]).exists():
        rel = index[card_id]
        path = report_path_for_relative(project_id, rel)
    else:
        path = ensure_card_report(project, board_id, card_id, card_title)
        rel = (
            load_index(project_id).get(card_id)
            or path.relative_to(reports_dir(project_id)).as_posix()
        )
    meta = _report_meta(project_id, card_id, rel, path)
    if meta["content"].strip():
        meta["source"] = "saved"
        return meta
    # Публичный отчёт пуст: показать рабочий .run.md (основание вердикта и
    # инсайтов после автоинтеграции), а если нет и его — заполненный шаблон.
    run_path = path.with_name(path.stem + RUN_EXT)
    run_text = ""
    if run_path.is_file():
        try:
            run_text = run_path.read_text(encoding="utf-8")
        except OSError:
            run_text = ""
    if run_text.strip():
        meta["content"] = run_text
        meta["source"] = "run"
        rel_dir = rel.rsplit("/", 1)[0] + "/" if "/" in rel else ""
        meta["run_relative_path"] = f"reports/{rel_dir}{run_path.name}"
    else:
        meta["content"] = report_scaffold(project, board_id, card_id, card_title)
        meta["source"] = "template"
    return meta


def write_report(
    project: Project, board_id: str, card_id: str, card_title: str, content: str
) -> dict[str, str]:
    project_id = project.id
    index = load_index(project_id)
    if card_id in index:
        path = report_path_for_relative(project_id, index[card_id])
    else:
        path = ensure_card_report(project, board_id, card_id, card_title)
        index = load_index(project_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    rel = index.get(card_id, path.relative_to(reports_dir(project_id)).as_posix())
    return _report_meta(project_id, card_id, rel, path)


def rename_report_for_card(
    project: Project, board_id: str, card_id: str, new_title: str
) -> None:
    project_id = project.id
    index = load_index(project_id)
    if card_id not in index:
        ensure_card_report(project, board_id, card_id, new_title)
        return

    old_rel = index[card_id]
    owner_slug = owner_slug_for_board(project, board_id)
    old_path = report_path_for_relative(project_id, old_rel)

    used = {
        Path(v).name
        for cid, v in index.items()
        if cid != card_id and v.startswith(f"{owner_slug}/")
    }
    new_name = _unique_card_filename(used, new_title)
    new_rel = f"{owner_slug}/{new_name}"

    if old_rel == new_rel:
        return

    new_path = report_path_for_relative(project_id, new_rel)
    new_path.parent.mkdir(parents=True, exist_ok=True)
    if old_path.exists() and not new_path.exists():
        old_path.rename(new_path)
    elif old_path.exists():
        new_path.write_text(old_path.read_text(encoding="utf-8"), encoding="utf-8")
        old_path.unlink()

    index[card_id] = new_rel
    save_index(project_id, index)


def delete_report(project_id: str, card_id: str) -> None:
    index = load_index(project_id)
    rel = index.pop(card_id, None)
    if rel:
        path = report_path_for_relative(project_id, rel)
        if path.exists():
            path.unlink()
        save_index(project_id, index)


def _report_dir_for_card(
    project: Project, board_id: str, card_id: str, card_title: str
) -> Path:
    project_id = project.id
    index = load_index(project_id)
    if card_id not in index:
        ensure_card_report(project, board_id, card_id, card_title)
        index = load_index(project_id)
    rel = index[card_id]
    report_path = report_path_for_relative(project_id, rel)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    return report_path.parent


def _safe_asset_name(name: str) -> str:
    name = Path(name).name
    if not name or name in (".", "..") or ".." in name:
        raise ValueError("Invalid asset name")
    return name


def save_report_asset(
    project: Project,
    board_id: str,
    card_id: str,
    card_title: str,
    data: bytes,
    content_type: str,
) -> dict[str, str]:
    if len(data) > MAX_ASSET_BYTES:
        raise ValueError(f"Image too large (max {MAX_ASSET_BYTES // (1024 * 1024)} MB)")
    mime = content_type.split(";")[0].strip().lower()
    ext = MIME_TO_EXT.get(mime)
    if not ext:
        raise ValueError(f"Unsupported image type: {mime}")

    report_dir = _report_dir_for_card(project, board_id, card_id, card_title)
    assets_dir = report_dir / ASSETS_DIR
    assets_dir.mkdir(parents=True, exist_ok=True)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"paste_{stamp}_{uuid4().hex[:6]}{ext}"
    (assets_dir / filename).write_bytes(data)

    markdown_path = f"{ASSETS_DIR}/{filename}"
    rel = load_index(project.id)[card_id]
    return {
        "markdown_path": markdown_path,
        "filename": filename,
        "storage_path": f"reports/{rel.rsplit('/', 1)[0]}/{markdown_path}",
    }


def resolve_report_asset_path(
    project: Project,
    board_id: str,
    card_id: str,
    card_title: str,
    asset_name: str,
) -> Path:
    safe = _safe_asset_name(asset_name)
    report_dir = _report_dir_for_card(project, board_id, card_id, card_title)
    path = (report_dir / ASSETS_DIR / safe).resolve()
    assets_root = (report_dir / ASSETS_DIR).resolve()
    if not str(path).startswith(str(assets_root)):
        raise ValueError("Invalid asset path")
    if not path.is_file():
        raise FileNotFoundError(safe)
    return path
