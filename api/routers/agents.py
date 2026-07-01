from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, HTTPException

from api.schemas import (
    AgentChatAnswerBody,
    AgentChatBody,
    AgentChatSettingsBody,
    CursorApiKeyBody,
    InboxConfiguredBody,
)
from koi.adapters.agent_chat_queue import (
    dequeue as dequeue_agent_chat_item,
    enqueue_question,
    find_item,
    list_for_project,
    list_pending,
    submit_answer,
)
from koi.services.agent_chat_runner import process_item
from koi.services.agent_chat_auto import try_auto_answer
from koi.adapters.settings_store import is_cursor_inbox_agent_mode
from koi.services.agent_chat_inbox import (
    inbox_task_message,
    notify_chat_inbox_wake,
    set_inbox_configured,
)
from koi.services.agent_chat_worker_ctl import (
    cursor_sdk_available,
    ensure_agent_worker,
    stop_agent_worker,
    worker_running,
)
from koi.adapters.agent_backends import backend_status
from koi.adapters.repository import load_project
from koi.adapters.settings_store import (
    AGENT_CHAT_MODES,
    get_agent_chat_mode,
    is_api_agent_mode,
    set_agent_chat_mode,
    set_cursor_api_key,
    settings_snapshot,
)

router = APIRouter(tags=["agents"])


def _run_agent_chat_item(item_id: str) -> None:
    process_item(item_id)


def _sync_agent_worker() -> bool:
    if is_api_agent_mode():
        return ensure_agent_worker()
    stop_agent_worker()
    return False


def _auto_answer_pending(project_id: str) -> None:
    for item in list_for_project(project_id, limit=10):
        if item.get("status") == "answered":
            continue
        auto = try_auto_answer(project_id, item["question"])
        if auto:
            try:
                submit_answer(item["id"], auto)
            except (KeyError, ValueError):
                pass


@router.get("/agent/backends")
def get_agent_backends():
    return backend_status()


@router.post("/agent-chat")
def post_agent_chat(body: AgentChatBody, background_tasks: BackgroundTasks) -> dict:
    if load_project(body.project_id, sync_reports=False) is None:
        raise HTTPException(404, "Project not found")
    try:
        item = enqueue_question(
            body.project_id,
            body.question,
            method_id=body.method_id,
            node_id=body.node_id,
        )
    except ValueError as e:
        raise HTTPException(400, str(e)) from e

    answered = process_item(item["id"])
    item = find_item(item["id"]) or item

    if not answered:
        background_tasks.add_task(_run_agent_chat_item, item["id"])
        if is_cursor_inbox_agent_mode() and item.get("status") != "answered":
            notify_chat_inbox_wake(agent_chat_id=item["id"])

    return {
        "ok": True,
        "item": item,
        "answered": item.get("status") == "answered",
        "inbox_message": (
            inbox_task_message(agent_chat_id=item["id"])
            if get_agent_chat_mode() == "cursor_inbox" and item.get("status") != "answered"
            else None
        ),
    }


@router.get("/agent-chat/pending")
def get_agent_chat_pending() -> dict:
    return {"items": list_pending()}


@router.get("/agent-chat")
def get_agent_chat(project_id: str) -> dict:
    if load_project(project_id, sync_reports=False) is None:
        raise HTTPException(404, "Project not found")
    _auto_answer_pending(project_id)
    return {"items": list_for_project(project_id)}


@router.patch("/agent-chat/{item_id}")
def patch_agent_chat_answer(item_id: str, body: AgentChatAnswerBody) -> dict:
    try:
        item = submit_answer(item_id, body.answer)
    except KeyError as e:
        raise HTTPException(404, str(e)) from e
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    return {"ok": True, "item": item}


@router.delete("/agent-chat/{item_id}")
def delete_agent_chat_item(item_id: str) -> dict:
    if not dequeue_agent_chat_item(item_id):
        raise HTTPException(404, f"Queue item not found: {item_id}")
    return {"ok": True}


@router.get("/settings")
def get_settings() -> dict:
    snap = settings_snapshot()
    snap["cursor_sdk_installed"] = cursor_sdk_available()
    snap["agent_worker_running"] = worker_running()
    return snap


@router.put("/settings/cursor-api-key")
def put_cursor_api_key(body: CursorApiKeyBody) -> dict:
    key = body.cursor_api_key.strip()
    set_cursor_api_key(key or None)
    running = _sync_agent_worker()
    snap = settings_snapshot()
    snap["agent_worker_running"] = running
    return {"ok": True, **snap}


@router.put("/settings/inbox-configured")
def put_inbox_configured(body: InboxConfiguredBody) -> dict:
    kind = (body.inbox_kind or "chat").strip().lower()
    if kind not in ("chat", "literature", "paper"):
        raise HTTPException(400, "inbox_kind must be 'chat', 'literature', or 'paper'")
    set_inbox_configured(body.configured, inbox_kind=kind)
    snap = settings_snapshot()
    snap["agent_worker_running"] = worker_running()
    return {"ok": True, **snap}


@router.put("/settings/agent-chat")
def put_agent_chat_settings(body: AgentChatSettingsBody) -> dict:
    if body.agent_chat_mode is not None:
        mode = body.agent_chat_mode.strip().lower()
        if mode not in AGENT_CHAT_MODES:
            raise HTTPException(
                400,
                f"agent_chat_mode must be one of: {', '.join(sorted(AGENT_CHAT_MODES))}",
            )
        set_agent_chat_mode(mode)
    if body.cursor_api_key is not None:
        set_cursor_api_key(body.cursor_api_key.strip() or None)
    running = _sync_agent_worker()
    snap = settings_snapshot()
    snap["agent_worker_running"] = running
    return {"ok": True, **snap}
