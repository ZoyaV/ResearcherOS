/**
 * Browser collaboration client backed by a real Yjs document.
 *
 * The server relays Yjs updates verbatim. Local DOM edits are applied once to
 * Y.Text; server echoes are unnecessary and therefore cannot move the caret.
 */

import { KoiApi } from "./api.js?v=20260826t";
import * as Y from "./vendor/yjs.mjs?v=13.6.27";
import { createPaperWebRtcMesh } from "./paper-webrtc.js?v=20260827e";

const NAME_KEY = "koi-collab-name";
const LOCAL_ORIGIN = Symbol("paper-collab-local");
const REMOTE_ORIGIN = Symbol("paper-collab-remote");
const P2P_ORIGIN = Symbol("paper-collab-p2p");
const RESET_ORIGIN = Symbol("paper-collab-reset");
const COMMENTS_SEED = Symbol("paper-collab-comments-seed");
const COMMENTS_WRITE = Symbol("paper-collab-comments-write");

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
  onComments,
  onConflict,
  onProposal,
  onStatus,
  onMaterialized,
  getComments,
  getLocalText,
  getLocalDirty,
} = {}) {
  const peerId = localPeerId();
  let socket = null;
  let ydoc = null;
  let ytext = null;
  let ycomments = null;
  let revision = 0;
  let peers = [];
  let connected = false;
  let synced = false;
  let closing = false;
  let pendingUpdates = 0;
  let projectId = "";
  let slug = "";
  let caretBefore = { start: 0, end: 0, value: "" };
  let crdtEpoch = "";
  let networkStarted = false;
  let networkStatus = {
    enabled: false,
    signaling: false,
    remotePeerCount: 0,
    roomId: "",
    gitCommit: "",
    error: "",
  };

  const mesh = createPaperWebRtcMesh({
    peerId,
    userName: localUserName(),
    refreshConfig: () =>
      projectId && slug ? KoiApi.getPaperCollabNetwork(projectId, slug, peerId) : null,
    getDocumentUpdate: () => (ydoc ? Y.encodeStateAsUpdate(ydoc) : null),
    getComments: () => getComments?.() || [],
    onComments: (payload) => onComments?.(payload),
    getText: () => ytext?.toString() || getLocalText?.() || "",
    applyRemoteText: (text) => replaceText(text, P2P_ORIGIN),
    applyRemoteSpan: (span) => applySpan(span, P2P_ORIGIN),
    reapplyLocalText: (text) => replaceText(text, LOCAL_ORIGIN),
    reapplyLocalSpan: (span) => applySpan(span, LOCAL_ORIGIN),
    applyRemoteUpdate: (update) => {
      if (ydoc) Y.applyUpdate(ydoc, update, P2P_ORIGIN);
    },
    adoptRemoteState: (update, metadata) => {
      send({
        type: "adopt_remote",
        update: bytesToBase64(update),
        crdt_epoch: metadata.crdt_epoch,
        expected_hash: "",
      });
    },
    onPresence: (presence) => onPresence?.([presence]),
    onStatus: (status) => {
      networkStatus = { ...networkStatus, ...status };
      emitStatus();
    },
  });

  function emitStatus() {
    onStatus?.({
      connected,
      revision,
      peers,
      peerCount: peers.length,
      network: networkStatus,
    });
  }

  function send(payload) {
    if (!socket || socket.readyState !== WebSocket.OPEN) return false;
    socket.send(JSON.stringify(payload));
    return true;
  }

  function applySpan(span, origin) {
    if (!ydoc || !ytext || !span) return false;
    const start = Number(span.start) || 0;
    const deleteLen = Number(span.delete_len) || 0;
    const insert = String(span.new_text || "");
    if (start < 0 || start > ytext.length) return false;
    if (deleteLen < 0 || start + deleteLen > ytext.length) return false;
    if (!deleteLen && !insert) return false;
    const pre = String(span.pre || "");
    if (pre) {
      const got = ytext.toString().slice(Math.max(0, start - pre.length), start);
      if (got !== pre) return false;
    }
    ydoc.transact(() => {
      if (deleteLen) ytext.delete(start, deleteLen);
      if (insert) ytext.insert(start, insert);
    }, origin);
    caretBefore = { ...caretBefore, value: ytext.toString() };
    return true;
  }

  function replaceText(text, origin) {
    if (!ydoc || !ytext || typeof text !== "string") return;
    if (!text && ytext.length) return;
    if (ytext.toString() === text) return;
    ydoc.transact(() => {
      if (ytext.length) ytext.delete(0, ytext.length);
      if (text) ytext.insert(0, text);
    }, origin);
    caretBefore = { ...caretBefore, value: ytext.toString() };
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

  function commentsFromYjs() {
    const comments = [];
    ycomments?.forEach((value) => {
      try {
        const item = typeof value === "string" ? JSON.parse(value) : value;
        if (item?.id) comments.push(item);
      } catch {
        /* ignore bad comment payload */
      }
    });
    return comments;
  }

  function seedComments() {
    if (!ydoc || !ycomments) return;
    const list = getComments?.() || [];
    ydoc.transact(() => {
      for (const comment of list) {
        if (comment?.id && !ycomments.has(comment.id)) {
          ycomments.set(comment.id, JSON.stringify(comment));
        }
      }
    }, COMMENTS_SEED);
  }

  function writeComments(comments, deletedIds = []) {
    if (!ydoc || !ycomments) return;
    ydoc.transact(() => {
      for (const commentId of deletedIds) {
        if (commentId) ycomments.delete(String(commentId));
      }
      for (const comment of comments || []) {
        if (comment?.id) ycomments.set(comment.id, JSON.stringify(comment));
      }
    }, COMMENTS_WRITE);
  }

  function emitCommentsFromYjs() {
    onComments?.({
      comments: commentsFromYjs(),
      deleted_ids: [],
      replace: true,
    });
  }

  function createDocument() {
    ydoc?.destroy();
    ydoc = new Y.Doc();
    ytext = ydoc.getText("content");
    ycomments = ydoc.getMap("comments");
    ytext.observe((_event, transaction) => publishText(transaction.origin));
    ycomments.observe((_event, transaction) => {
      if (
        transaction.origin === LOCAL_ORIGIN ||
        transaction.origin === COMMENTS_SEED ||
        transaction.origin === COMMENTS_WRITE ||
        transaction.origin === RESET_ORIGIN
      ) {
        return;
      }
      emitCommentsFromYjs();
    });
    ydoc.on("update", (update, origin) => {
      if (origin === COMMENTS_SEED || origin === COMMENTS_WRITE) return;
      if (origin === LOCAL_ORIGIN || origin === P2P_ORIGIN) {
        if (send({ type: "crdt_update", update: bytesToBase64(update) })) {
          pendingUpdates += 1;
        }
      }
      if (origin === LOCAL_ORIGIN || origin === REMOTE_ORIGIN) {
        mesh.broadcastUpdate(update);
      }
    });
  }

  async function startNetwork() {
    if (networkStarted || !projectId || !slug) return;
    networkStarted = true;
    try {
      const config = await KoiApi.getPaperCollabNetwork(projectId, slug, peerId);
      crdtEpoch = String(config.crdt_epoch || crdtEpoch);
      networkStatus = {
        ...networkStatus,
        enabled: Boolean(config.enabled),
        roomId: String(config.room_id || ""),
        gitCommit: String(config.git_commit || ""),
      };
      emitStatus();
      const local = getLocalText?.() || "";
      if (local && ytext && ytext.toString() !== local) {
        replaceText(local, RESET_ORIGIN);
      }
      const gitDirty =
        Boolean(config.document_hash) &&
        Boolean(config.base_document_hash) &&
        config.document_hash !== config.base_document_hash;
      await mesh.connect(config);
      if (gitDirty) mesh.markPublishSnapshot();
      else if (getLocalDirty?.()) mesh.markLocalDirty();
      mesh.broadcastTex();
      if (!gitDirty) mesh.requestTexFromPeers();
    } catch (error) {
      networkStatus = {
        ...networkStatus,
        error: error?.message || "Не удалось запустить P2P",
      };
      emitStatus();
    }
  }

  function applyReset(message) {
    createDocument();
    Y.applyUpdate(ydoc, base64ToBytes(String(message.update || "")), RESET_ORIGIN);
    seedComments();
    synced = true;
    revision = Number(message.revision) || 0;
    crdtEpoch = String(message.crdt_epoch || crdtEpoch);
    mesh.noteLocalState({
      crdt_epoch: crdtEpoch,
      document_hash: String(message.hash || ""),
    });
    publishText(REMOTE_ORIGIN);
    emitStatus();
  }

  function noteServerUpdate(message) {
    if (message.crdt_epoch) {
      crdtEpoch = String(message.crdt_epoch);
      mesh.noteLocalState({
        crdt_epoch: crdtEpoch,
        document_hash: String(message.hash || ""),
      });
    }
  }

  function handleMessage(message) {
    if (!message || typeof message !== "object") return;
    if (message.type === "sync") {
      Y.applyUpdate(ydoc, base64ToBytes(String(message.update || "")), REMOTE_ORIGIN);
      synced = true;
      revision = Number(message.revision) || 0;
      noteServerUpdate(message);
      if (ytext?.toString()) publishText(REMOTE_ORIGIN);
      emitStatus();
      seedComments();
      void startNetwork();
      return;
    }
    if (message.type === "crdt_update") {
      Y.applyUpdate(ydoc, base64ToBytes(String(message.update || "")), REMOTE_ORIGIN);
      revision = Number(message.revision) || revision;
      noteServerUpdate(message);
      emitStatus();
      return;
    }
    if (message.type === "reset_sync") {
      applyReset(message);
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
    if (message.type === "comments") {
      onComments?.({
        comments: Array.isArray(message.comments) ? message.comments : [],
        deleted_ids: Array.isArray(message.deleted_ids) ? message.deleted_ids : [],
      });
      return;
    }
    if (message.type === "conflict") {
      onConflict?.(message);
      return;
    }
    if (message.type === "network_error") {
      networkStatus = {
        ...networkStatus,
        error: message.reason || "P2P state отклонён",
      };
      emitStatus();
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
    const reuse =
      Boolean(ydoc) &&
      projectId === nextProjectId &&
      slug === nextSlug &&
      !closing;
    if (reuse) {
      const previous = socket;
      socket = null;
      try {
        previous?.close();
      } catch {
        /* already closed */
      }
      connected = false;
    } else {
      await disconnect();
      projectId = nextProjectId;
      slug = nextSlug;
      pendingUpdates = 0;
      crdtEpoch = "";
      networkStarted = false;
      createDocument();
    }
    closing = false;
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
    const ws = socket;
    socket.addEventListener("close", () => {
      if (socket !== ws) return;
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
    ycomments = null;
    connected = false;
    synced = false;
    pendingUpdates = 0;
    peers = [];
    crdtEpoch = "";
    networkStarted = false;
    mesh.disconnect();
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
    if (!ydoc || !ytext) return;
    const before = caretBefore.value ?? "";
    const after = textarea?.value ?? "";
    const span = inputSpan(textarea, event, caretBefore);
    caretBefore = {
      start: textarea?.selectionStart ?? 0,
      end: textarea?.selectionEnd ?? 0,
      value: after,
    };
    if (!span || (!span.delete_len && !span.new_text)) return;
    mesh.noteLocalTyped();
    if (!ytext.toString() && after) {
      replaceText(after, LOCAL_ORIGIN);
      mesh.broadcastTex();
      return;
    }
    if (ytext.toString() !== before) {
      replaceText(after, LOCAL_ORIGIN);
      mesh.broadcastTex();
      return;
    }
    const base_len = ytext.length;
    const pre = before.slice(Math.max(0, span.start - 24), span.start);
    ydoc.transact(() => {
      if (span.delete_len) ytext.delete(span.start, span.delete_len);
      if (span.new_text) ytext.insert(span.start, span.new_text);
    }, LOCAL_ORIGIN);
    mesh.broadcastTexSpan({ ...span, base_len, pre });
  }

  return {
    peerId,
    connect,
    disconnect,
    rememberCaret,
    queueInput,
    sendPresence: (presence) => {
      mesh.broadcastPresence(presence);
      return send({ type: "presence", ...presence });
    },
    publishComments: (payload) => {
      const frame = {
        comments: payload?.comments || getComments?.() || [],
        deleted_ids: payload?.deleted_ids || [],
      };
      writeComments(frame.comments, frame.deleted_ids);
      mesh.broadcastComments(frame);
      return send({ type: "comments", ...frame });
    },
    requestFlush: () => send({ type: "flush" }),
    isActive: () =>
      (connected && synced) || Number(networkStatus.relayPeerCount) > 0,
    hasPendingEdit: () => pendingUpdates > 0,
    currentRevision: () => revision,
    currentText: () => ytext?.toString() ?? "",
    noteAcked: () => {},
    mapOffset,
  };
}
