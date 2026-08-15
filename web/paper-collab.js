/**
 * Browser collaboration client backed by a real Yjs document.
 *
 * The server relays Yjs updates verbatim. Local DOM edits are applied once to
 * Y.Text; server echoes are unnecessary and therefore cannot move the caret.
 */

import { KoiApi } from "./api.js?v=20260815d";
import * as Y from "./vendor/yjs.mjs?v=13.6.27";

const NAME_KEY = "koi-collab-name";
const LOCAL_ORIGIN = Symbol("paper-collab-local");
const REMOTE_ORIGIN = Symbol("paper-collab-remote");

function randomId(prefix) {
  return `${prefix}-${Math.random().toString(16).slice(2, 10)}`;
}

export function localPeerId() {
  try {
    const existing = sessionStorage.getItem("koi-collab-peer-tab");
    if (existing) return existing;
    const created = randomId("peer");
    sessionStorage.setItem("koi-collab-peer-tab", created);
    return created;
  } catch {
    return randomId("peer");
  }
}

export function localUserName() {
  try {
    return localStorage.getItem(NAME_KEY) || "local";
  } catch {
    return "local";
  }
}

export function prefixSuffixSpan(oldText, newText) {
  let start = 0;
  const limit = Math.min(oldText.length, newText.length);
  while (start < limit && oldText[start] === newText[start]) start += 1;
  let oldEnd = oldText.length;
  let newEnd = newText.length;
  while (oldEnd > start && newEnd > start && oldText[oldEnd - 1] === newText[newEnd - 1]) {
    oldEnd -= 1;
    newEnd -= 1;
  }
  return { start, delete_len: oldEnd - start, new_text: newText.slice(start, newEnd) };
}

function mapOffset(oldText, newText, offset) {
  const span = prefixSuffixSpan(oldText, newText);
  const oldEnd = span.start + span.delete_len;
  const newEnd = span.start + span.new_text.length;
  if (offset <= span.start) return offset;
  if (offset >= oldEnd) return newEnd + (offset - oldEnd);
  return newEnd;
}

function bytesToBase64(bytes) {
  let binary = "";
  const chunk = 0x8000;
  for (let i = 0; i < bytes.length; i += chunk) {
    binary += String.fromCharCode(...bytes.subarray(i, i + chunk));
  }
  return btoa(binary);
}

function base64ToBytes(value) {
  const binary = atob(value);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i);
  return bytes;
}

function inputSpan(textarea, event, before) {
  const after = textarea?.value ?? "";
  const old = before?.value ?? "";
  const start = Math.max(0, before?.start ?? 0);
  const end = Math.max(start, before?.end ?? start);
  const selected = end - start;
  const type = event?.inputType || "";

  if (type === "insertText" || type === "insertCompositionText") {
    return { start, delete_len: selected, new_text: event.data || "" };
  }
  if (type === "insertLineBreak" || type === "insertParagraph") {
    return { start, delete_len: selected, new_text: "\n" };
  }
  if (type === "deleteContentBackward") {
    if (selected) return { start, delete_len: selected, new_text: "" };
    return start > 0 ? { start: start - 1, delete_len: 1, new_text: "" } : null;
  }
  if (type === "deleteContentForward") {
    if (selected) return { start, delete_len: selected, new_text: "" };
    return start < old.length ? { start, delete_len: 1, new_text: "" } : null;
  }
  if (type === "deleteByCut" || type === "deleteByDrag") {
    return selected ? { start, delete_len: selected, new_text: "" } : null;
  }
  if (type === "insertFromPaste" || type === "insertFromDrop") {
    const insertedLength = after.length - old.length + selected;
    if (insertedLength < 0) return null;
    return {
      start,
      delete_len: selected,
      new_text: after.slice(start, start + insertedLength),
    };
  }

  // Undo/redo and browser-specific input types may replace several ranges.
  // This fallback is safe because it compares one atomic DOM input against
  // the exact Y.Text value from immediately before that input.
  return prefixSuffixSpan(old, after);
}

export function createPaperCollabClient({
  onState,
  onPresence,
  onConflict,
  onProposal,
  onStatus,
  onMaterialized,
} = {}) {
  const peerId = localPeerId();
  let socket = null;
  let ydoc = null;
  let ytext = null;
  let revision = 0;
  let peers = [];
  let connected = false;
  let synced = false;
  let closing = false;
  let pendingUpdates = 0;
  let projectId = "";
  let slug = "";
  let caretBefore = { start: 0, end: 0, value: "" };

  function emitStatus() {
    onStatus?.({ connected, revision, peers, peerCount: peers.length });
  }

  function send(payload) {
    if (!socket || socket.readyState !== WebSocket.OPEN) return false;
    socket.send(JSON.stringify(payload));
    return true;
  }

  function publishText(origin) {
    const text = ytext?.toString() ?? "";
    onState?.({
      revision,
      text,
      hash: "",
      applyToEditor: origin !== LOCAL_ORIGIN,
      origin: origin === LOCAL_ORIGIN ? peerId : "",
    });
  }

  function createDocument() {
    ydoc?.destroy();
    ydoc = new Y.Doc();
    ytext = ydoc.getText("content");
    ytext.observe((_event, transaction) => publishText(transaction.origin));
    ydoc.on("update", (update, origin) => {
      if (origin !== LOCAL_ORIGIN) return;
      if (send({ type: "crdt_update", update: bytesToBase64(update) })) {
        pendingUpdates += 1;
      }
    });
  }

  function handleMessage(message) {
    if (!message || typeof message !== "object") return;
    if (message.type === "sync") {
      Y.applyUpdate(ydoc, base64ToBytes(String(message.update || "")), REMOTE_ORIGIN);
      synced = true;
      revision = Number(message.revision) || 0;
      publishText(REMOTE_ORIGIN);
      emitStatus();
      return;
    }
    if (message.type === "crdt_update") {
      Y.applyUpdate(ydoc, base64ToBytes(String(message.update || "")), REMOTE_ORIGIN);
      revision = Number(message.revision) || revision;
      emitStatus();
      return;
    }
    if (message.type === "ack") {
      pendingUpdates = Math.max(0, pendingUpdates - 1);
      revision = Number(message.revision) || revision;
      emitStatus();
      return;
    }
    if (message.type === "hello") {
      connected = true;
      revision = Number(message.revision) || revision;
      peers = Array.isArray(message.peers) ? message.peers : peers;
      if ("proposal" in message) onProposal?.(message.proposal || null);
      emitStatus();
      return;
    }
    if (message.type === "presence") {
      peers = Array.isArray(message.peers) ? message.peers : [];
      onPresence?.(peers);
      emitStatus();
      return;
    }
    if (message.type === "conflict") {
      onConflict?.(message);
      return;
    }
    if (message.type === "proposal") {
      onProposal?.(message.proposal || null);
      return;
    }
    if (message.type === "proposal_resolved") {
      onProposal?.(null, message.resolution || "");
      return;
    }
    if (message.type === "proposal_hunk_resolved") {
      onProposal?.(message.proposal || null, message.resolution || "");
      return;
    }
    if (message.type === "materialized") onMaterialized?.(message);
  }

  function openSocket(url) {
    return new Promise((resolve, reject) => {
      const ws = new WebSocket(url);
      const buffered = [];
      const buffer = (event) => buffered.push(event);
      ws.addEventListener("message", buffer);
      ws.addEventListener("open", () => {
        resolve({ ws, buffered, buffer });
      }, { once: true });
      ws.addEventListener("error", () => reject(new Error("collab websocket failed")), {
        once: true,
      });
    });
  }

  async function connect(nextProjectId, nextSlug) {
    await disconnect();
    projectId = nextProjectId;
    slug = nextSlug;
    closing = false;
    synced = false;
    pendingUpdates = 0;
    createDocument();
    const params = { peer: peerId, user: localUserName(), actor: "human" };
    const primary = KoiApi.paperCollabWsUrl(projectId, slug, params);
    const fallback = KoiApi.paperCollabWsFallbackUrl(projectId, slug, params);
    let opened;
    try {
      opened = await openSocket(primary);
    } catch {
      opened = await openSocket(fallback);
    }
    socket = opened.ws;
    connected = true;
    socket.addEventListener("message", (event) => {
      try {
        handleMessage(JSON.parse(event.data));
      } catch {
        /* ignore malformed frames */
      }
    });
    socket.removeEventListener("message", opened.buffer);
    for (const event of opened.buffered) {
      try {
        handleMessage(JSON.parse(event.data));
      } catch {
        /* ignore malformed frames */
      }
    }
    socket.addEventListener("close", () => {
      connected = false;
      synced = false;
      emitStatus();
      if (!closing) {
        setTimeout(() => {
          if (!closing && projectId && slug) void connect(projectId, slug);
        }, 1200);
      }
    });
    emitStatus();
    return true;
  }

  async function disconnect() {
    closing = true;
    if (socket) socket.close();
    socket = null;
    ydoc?.destroy();
    ydoc = null;
    ytext = null;
    connected = false;
    synced = false;
    pendingUpdates = 0;
    peers = [];
    onProposal?.(null);
    emitStatus();
  }

  function rememberCaret(textarea) {
    if (!textarea) return;
    caretBefore = {
      start: textarea.selectionStart ?? 0,
      end: textarea.selectionEnd ?? 0,
      value: textarea.value ?? "",
    };
  }

  function queueInput(textarea, event) {
    if (!synced || !ydoc || !ytext) return;
    const span = inputSpan(textarea, event, caretBefore);
    caretBefore = {
      start: textarea?.selectionStart ?? 0,
      end: textarea?.selectionEnd ?? 0,
      value: textarea?.value ?? "",
    };
    if (!span || (!span.delete_len && !span.new_text)) return;
    ydoc.transact(() => {
      if (span.delete_len) ytext.delete(span.start, span.delete_len);
      if (span.new_text) ytext.insert(span.start, span.new_text);
    }, LOCAL_ORIGIN);
  }

  return {
    peerId,
    connect,
    disconnect,
    rememberCaret,
    queueInput,
    sendPresence: (presence) => send({ type: "presence", ...presence }),
    requestFlush: () => send({ type: "flush" }),
    isActive: () => connected && synced,
    hasPendingEdit: () => pendingUpdates > 0,
    currentRevision: () => revision,
    currentText: () => ytext?.toString() ?? "",
    noteAcked: () => {},
    mapOffset,
  };
}
