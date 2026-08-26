/**
 * Full-mesh WebRTC transport for Yjs updates between ResearcherOS instances.
 *
 * The signaling socket carries only SDP/ICE metadata. Paper updates and
 * presence use encrypted RTCDataChannels.
 */

function bytesToBase64(bytes) {
  let binary = "";
  const chunk = 0x8000;
  for (let index = 0; index < bytes.length; index += chunk) {
    binary += String.fromCharCode(...bytes.subarray(index, index + chunk));
  }
  return btoa(binary);
}

function base64ToBytes(value) {
  const binary = atob(value);
  const bytes = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) bytes[index] = binary.charCodeAt(index);
  return bytes;
}

function updateId(bytes) {
  let value = 2166136261;
  for (const byte of bytes) {
    value ^= byte;
    value = Math.imul(value, 16777619);
  }
  return `${bytes.length}:${(value >>> 0).toString(16)}`;
}

function isPrivateIPv4(host) {
  return /^(192\.168\.|10\.|172\.(1[6-9]|2\d|3[01])\.)/.test(host || "");
}

function signalingLanHint(signalingUrl) {
  try {
    const host = new URL(signalingUrl).hostname;
    return isPrivateIPv4(host) ? host : "";
  } catch {
    return "";
  }
}

function withLanAddress(candidateJson, lanIp) {
  const line = String(candidateJson?.candidate || "");
  if (!lanIp || !line.includes(".local")) return null;
  return { ...candidateJson, candidate: line.replace(/\S+\.local/g, lanIp) };
}

export function createPaperWebRtcMesh({
  peerId,
  userName,
  getDocumentUpdate,
  applyRemoteUpdate,
  adoptRemoteState,
  refreshConfig,
  getComments,
  onComments,
  getText,
  applyRemoteText,
  applyRemoteSpan,
  reapplyLocalText,
  reapplyLocalSpan,
  onPresence,
  onStatus,
} = {}) {
  let config = null;
  let signal = null;
  let authorityPeerId = "";
  let closing = false;
  let heartbeat = null;
  let reconnectTimer = null;
  const connections = new Map();
  const remoteMetadata = new Map();
  const pendingIceCandidates = new Map();
  const seenUpdates = new Set();
  const queuedUpdates = [];
  const queuedLocalSpans = [];
  let queuedLocalSnapshot = "";
  let adoptingEpoch = "";
  let adoptingPeerId = "";
  let networkError = "";
  let stallTimer = null;
  const relayPeers = new Set();
  const crdtPeers = new Set();
  const crdtPendingPeers = new Set();
  const lastTexSeq = new Map();
  const resyncAt = new Map();
  const lastTexSent = new Map();
  const forcedResync = new Set();
  const needSnapshot = new Set();
  let typedAt = 0;
  const texChunks = new Map();
  const syncChunks = new Map();
  const updateChunks = new Map();
  let localTexSeq = 0;
  let texBackupTimer = null;
  const RELAY_LIMIT = 100000;
  const TEX_BACKUP_MS = 650;

  async function flushIceCandidates(remotePeerId, pc) {
    const queued = pendingIceCandidates.get(remotePeerId) || [];
    pendingIceCandidates.delete(remotePeerId);
    for (const candidate of queued) {
      try {
        await pc.addIceCandidate(candidate);
      } catch (error) {
        setError(error?.message || "WebRTC ICE candidate rejected");
      }
    }
  }

  async function addRemoteIceCandidate(remotePeerId, candidate) {
    const entry = connections.get(remotePeerId);
    const pc = entry?.pc || createConnection(remotePeerId, false);
    const rewritten = withLanAddress(candidate, peerLanIp(remotePeerId)) || candidate;
    if (!pc.remoteDescription) {
      const queued = pendingIceCandidates.get(remotePeerId) || [];
      queued.push(rewritten);
      pendingIceCandidates.set(remotePeerId, queued);
      return;
    }
    try {
      await pc.addIceCandidate(rewritten);
    } catch (error) {
      setError(error?.message || "WebRTC ICE candidate rejected");
    }
  }

  function shouldOffer(remotePeerId) {
    return String(peerId) > String(remotePeerId);
  }

  function schedulePeerOffer(remotePeerId) {
    if (!shouldOffer(remotePeerId)) return;
    setTimeout(() => {
      if (closing) return;
      const entry = connections.get(remotePeerId);
      const channelOpen = entry?.channel?.readyState === "open";
      const state = entry?.pc?.connectionState || "new";
      if (channelOpen || ["connected", "connecting"].includes(state)) return;
      const pc = entry?.pc;
      if (pc?.localDescription || pc?.remoteDescription) return;
      void offer(remotePeerId).catch((error) =>
        setError(error?.message || "WebRTC offer failed")
      );
    }, 1500);
  }

  function relayOnly() {
    const url = String(config?.signaling_url || "");
    return url.startsWith("wss://") || !signalingLanHint(url);
  }

  async function connectToPeer(remotePeerId, { force = false } = {}) {
    if (!remotePeerId || remotePeerId === peerId) return;
    const remote = remoteMetadata.get(remotePeerId) || {};
    if (relayOnly()) {
      startRelay(remotePeerId, { force });
      return;
    }
    if (!validatePeer(remote)) return;
    if (!force && !shouldOffer(remotePeerId)) return;
    try {
      await offer(remotePeerId);
      schedulePeerOffer(remotePeerId);
    } catch (error) {
      setError(error?.message || "WebRTC offer failed");
    }
  }

  function peerLanIp(remotePeerId) {
    const remote = remoteMetadata.get(remotePeerId) || {};
    if (isPrivateIPv4(remote.lan_ip)) return remote.lan_ip;
    return signalingLanHint(config?.signaling_url);
  }

  function publishIceCandidate(remotePeerId, candidateJson) {
    if (!candidateJson?.candidate) return;
    sendSignal({
      type: "ice_candidate",
      to: remotePeerId,
      payload: { candidate: candidateJson },
    });
    const rewritten = withLanAddress(candidateJson, config?.lan_ip);
    if (rewritten) {
      sendSignal({
        type: "ice_candidate",
        to: remotePeerId,
        payload: { candidate: rewritten },
      });
    }
  }

  function transportSnapshot() {
    const ices = [...connections.values()].map(({ pc }) => pc?.iceConnectionState).filter(Boolean);
    const conns = [...connections.values()].map(({ pc }) => pc?.connectionState).filter(Boolean);
    return {
      signalingPeerCount: remoteMetadata.size,
      iceState: ices[0] || (remoteMetadata.size ? "no-pc" : "idle"),
      connectionState: conns[0] || "",
    };
  }

  function emitStatus() {
    const connectedPeers = [...connections.values()].filter(
      ({ channel }) => channel?.readyState === "open"
    ).length;
    onStatus?.({
      enabled: Boolean(config?.enabled),
      signaling: signal?.readyState === WebSocket.OPEN,
      remotePeerCount: connectedPeers + relayPeers.size,
      relayPeerCount: relayPeers.size,
      crdtPeerCount: crdtPeers.size,
      crdtPendingPeerCount: crdtPendingPeers.size,
      authorityPeerId,
      roomId: String(config?.room_id || ""),
      gitCommit: String(config?.git_commit || ""),
      error: networkError,
      ...transportSnapshot(),
    });
  }

  function armStallWatch() {
    if (stallTimer) clearTimeout(stallTimer);
    stallTimer = setTimeout(() => {
      const open = [...connections.values()].some(
        ({ channel }) => channel?.readyState === "open"
      );
      if (open || closing) return;
      const snap = transportSnapshot();
      if (!snap.signalingPeerCount) {
        setError("P2P: signaling не видит второго пира");
        return;
      }
      for (const id of remoteMetadata.keys()) startRelay(id, { force: true });
    }, 8000);
  }

  function forgetRemotePeers() {
    remoteMetadata.clear();
    relayPeers.clear();
    crdtPeers.clear();
    crdtPendingPeers.clear();
    lastTexSent.clear();
    lastTexSeq.clear();
    resyncAt.clear();
    forcedResync.clear();
    needSnapshot.clear();
  }

  function wakeSignal() {
    if (closing || !config?.enabled) return;
    if (signal?.readyState === WebSocket.OPEN) {
      sendSignal({ type: "heartbeat" });
      for (const id of remoteMetadata.keys()) startRelay(id, { force: true });
      return;
    }
    if (signal?.readyState === WebSocket.CONNECTING) return;
    void openSignal();
  }

  function commentsFrame(payload = {}) {
    return {
      type: "comments",
      comments: Array.isArray(payload.comments) ? payload.comments : getComments?.() || [],
      deleted_ids: Array.isArray(payload.deleted_ids) ? payload.deleted_ids : [],
    };
  }

  function sendCommentsOn(channel) {
    sendChannel(channel, commentsFrame());
  }

  function sendCommentsTo(remotePeerId) {
    const frame = commentsFrame();
    if (!frame.comments.length && !frame.deleted_ids.length) return;
    const channel = connections.get(remotePeerId)?.channel;
    if (channel?.readyState === "open") {
      sendChannel(channel, frame);
      return;
    }
    sendRelay(remotePeerId, frame);
  }

  function texFrame() {
    return {
      type: "tex",
      text: getText?.() || "",
      dirty: Boolean(config?.publish_snapshot || config?.local_dirty),
      seq: localTexSeq,
      edited_at: typedAt,
    };
  }

  function noteRemoteSeq(fromPeer, seq) {
    const n = Number(seq);
    if (!Number.isFinite(n)) return;
    const prev = lastTexSeq.get(fromPeer) ?? -1;
    if (n > prev) lastTexSeq.set(fromPeer, n);
  }

  function isStaleTex(fromPeer, seq, { allowEqual = false } = {}) {
    if (seq == null || seq === "") return false;
    const n = Number(seq);
    if (!Number.isFinite(n)) return false;
    const prev = lastTexSeq.get(fromPeer) ?? -1;
    return allowEqual ? n < prev : n <= prev;
  }

  function requestResync(fromPeer, { adopt = false } = {}) {
    const now = Date.now();
    if (now - (resyncAt.get(fromPeer) || 0) < 250) return;
    resyncAt.set(fromPeer, now);
    if (adopt) needSnapshot.add(fromPeer);
    sendRelay(fromPeer, { type: "tex_resync" });
  }

  function scheduleTexBackup() {
    if (texBackupTimer) clearTimeout(texBackupTimer);
    const hasSnapshotPeer = [...relayPeers].some(
      (peer) => !crdtPeers.has(peer) && !crdtPendingPeers.has(peer)
    );
    if (closing || !config?.local_dirty || !hasSnapshotPeer) return;
    texBackupTimer = setTimeout(() => {
      texBackupTimer = null;
      if (closing || !config?.local_dirty) return;
      broadcastTex({ scheduleBackup: false });
    }, TEX_BACKUP_MS);
  }

  function sendTexTo(remotePeerId, { force = false } = {}) {
    const frame = texFrame();
    if (!frame.text) return;
    const now = Date.now();
    if (!force && now - (lastTexSent.get(remotePeerId) || 0) < 1500) return;
    lastTexSent.set(remotePeerId, now);
    const channel = connections.get(remotePeerId)?.channel;
    if (channel?.readyState === "open") {
      sendChannel(channel, frame);
      return;
    }
    sendRelay(remotePeerId, frame);
  }

  function adoptRemoteText(text, fromPeer, seq, meta = {}) {
    if (typeof text !== "string" || !text) return;
    const local = getText?.() || "";
    if (local === text) {
      forcedResync.delete(fromPeer);
      needSnapshot.delete(fromPeer);
      noteRemoteSeq(fromPeer, seq);
      return;
    }
    const force = forcedResync.delete(fromPeer) || needSnapshot.delete(fromPeer);
    const remoteAt = Number(meta.edited_at) || 0;
    if (typedAt && local && !force && remoteAt <= typedAt) return;
    const remoteDirty = Boolean(meta.dirty || meta.tex_dirty);
    if (!force && local && !remoteDirty && config?.local_dirty) return;
    if (!force && local && text.length < Math.min(32, local.length)) return;
    applyRemoteText?.(text);
    if (remoteAt > typedAt) typedAt = remoteAt;
    noteRemoteSeq(fromPeer, seq);
  }

  function broadcastTex({ scheduleBackup = true } = {}) {
    if (adoptingEpoch) {
      queuedLocalSnapshot = getText?.() || queuedLocalSnapshot;
      return;
    }
    localTexSeq += 1;
    for (const remotePeerId of relayPeers) {
      if (!crdtPeers.has(remotePeerId) && !crdtPendingPeers.has(remotePeerId)) {
        sendTexTo(remotePeerId, { force: true });
      }
    }
    if (scheduleBackup) scheduleTexBackup();
  }

  function requestTexFromPeers() {
    for (const remotePeerId of relayPeers) requestResync(remotePeerId);
  }

  function broadcastTexSpan(span) {
    if (!span) return;
    if (adoptingEpoch) {
      queuedLocalSpans.push({ ...span });
      return;
    }
    localTexSeq += 1;
    const payload = {
      type: "tex_span",
      start: Number(span.start) || 0,
      delete_len: Number(span.delete_len) || 0,
      new_text: String(span.new_text || ""),
      seq: localTexSeq,
      base_len: Number(span.base_len),
      pre: String(span.pre || ""),
    };
    if (!payload.delete_len && !payload.new_text) return;
    for (const remotePeerId of relayPeers) {
      if (!crdtPeers.has(remotePeerId) && !crdtPendingPeers.has(remotePeerId)) {
        sendRelay(remotePeerId, payload);
      }
    }
    scheduleTexBackup();
  }

  function broadcastComments(payload) {
    const frame = commentsFrame(payload);
    for (const { channel } of connections.values()) sendChannel(channel, frame);
    for (const remotePeerId of relayPeers) sendRelay(remotePeerId, frame);
  }

  function relayEnvelope(remotePeerId, payload) {
    return { type: "relay", to: remotePeerId, payload };
  }

  function sendChunkedTex(remotePeerId, payload) {
    const text = String(payload.text || "");
    if (!text) return false;
    const id = `${peerId}-${payload.seq ?? localTexSeq}-${Date.now()}`;
    let size = 24000;
    while (size >= 2000) {
      const n = Math.ceil(text.length / size);
      const frames = [];
      let tooBig = false;
      for (let i = 0; i < n; i += 1) {
        const piece = {
          type: "tex_chunk",
          id,
          i,
          n,
          seq: payload.seq,
          dirty: payload.dirty,
          edited_at: payload.edited_at,
          text: text.slice(i * size, i * size + size),
        };
        if (JSON.stringify(relayEnvelope(remotePeerId, piece)).length > RELAY_LIMIT) {
          tooBig = true;
          break;
        }
        frames.push(piece);
      }
      if (!tooBig) {
        return frames.every((piece) => sendSignal(relayEnvelope(remotePeerId, piece)));
      }
      size = Math.floor(size / 2);
    }
    return false;
  }

  function sendRelay(remotePeerId, payload) {
    const envelope = relayEnvelope(remotePeerId, payload);
    const body = JSON.stringify(envelope);
    // API Gateway drops the socket on frames above 128 KB.
    if (body.length > RELAY_LIMIT) {
      if (payload?.type === "tex" && payload.text) return sendChunkedTex(remotePeerId, payload);
      if (payload?.type === "hello" && payload.text) {
        const { text, tex_dirty, seq, ...rest } = payload;
        sendRelay(remotePeerId, rest);
        return sendChunkedTex(remotePeerId, { type: "tex", text, dirty: tex_dirty, seq });
      }
      return false;
    }
    return sendSignal(envelope);
  }

  function adoptChunk(fromPeer, message) {
    const id = String(message.id || "");
    if (!id) return;
    const key = `${fromPeer}:${id}`;
    const n = Number(message.n) || 0;
    const i = Number(message.i);
    if (!n || !Number.isFinite(i) || i < 0 || i >= n) return;
    const rec = texChunks.get(key) || {
      parts: Array(n).fill(null),
      n,
      seq: message.seq,
      dirty: false,
      edited_at: 0,
    };
    rec.parts[i] = String(message.text || "");
    rec.dirty = rec.dirty || Boolean(message.dirty || message.tex_dirty);
    rec.edited_at = Math.max(rec.edited_at, Number(message.edited_at) || 0);
    texChunks.set(key, rec);
    if (rec.parts.some((part) => part == null)) return;
    texChunks.delete(key);
    if (isStaleTex(fromPeer, rec.seq, { allowEqual: true })) return;
    adoptRemoteText(rec.parts.join(""), fromPeer, rec.seq, rec);
  }

  function startRelay(remotePeerId, { force = false } = {}) {
    if (!remotePeerId || remotePeerId === peerId || closing) return;
    const already = relayPeers.has(remotePeerId);
    relayPeers.add(remotePeerId);
    if (stallTimer) clearTimeout(stallTimer);
    networkError = "";
    if (!already || force) {
      const snapshot = commentsFrame();
      sendRelay(remotePeerId, {
        type: "hello",
        metadata: publicMetadata(),
        comments: snapshot.comments,
        deleted_ids: snapshot.deleted_ids,
      });
    }
    sendCommentsTo(remotePeerId);
    const remote = remoteMetadata.get(remotePeerId) || {};
    const canSyncCrdt =
      compatibleGit(remote) && Boolean(remote.crdt_epoch) && Boolean(config?.crdt_epoch);
    if (canSyncCrdt) {
      if (peerId === authorityPeerId) sendRelaySync(remotePeerId);
    } else {
      sendTexTo(remotePeerId, { force: true });
      if (!config?.publish_snapshot) {
        requestResync(remotePeerId, { adopt: !(getText?.() || "") });
      }
    }
    emitStatus();
  }

  function handleRelayPayload(fromPeer, payload) {
    if (!payload || typeof payload !== "object") return;
    relayPeers.add(fromPeer);
    if (stallTimer) clearTimeout(stallTimer);
    networkError = "";
    handleChannelMessage(fromPeer, { data: JSON.stringify(payload) });
  }

  function sendSignal(payload) {
    if (signal?.readyState !== WebSocket.OPEN) return false;
    signal.send(JSON.stringify(payload));
    return true;
  }

  function sendChannel(channel, payload) {
    if (channel?.readyState !== "open") return false;
    channel.send(JSON.stringify(payload));
    return true;
  }

  function rememberUpdate(bytes) {
    const id = updateId(bytes);
    if (seenUpdates.has(id)) return null;
    seenUpdates.add(id);
    if (seenUpdates.size > 2000) {
      const oldest = seenUpdates.values().next().value;
      seenUpdates.delete(oldest);
    }
    return id;
  }

  function compatibleGit(remote) {
    return String(remote?.git_commit || "") === String(config?.git_commit || "");
  }

  function setError(message) {
    networkError = message || "";
    emitStatus();
  }

  function validatePeer(remote) {
    if (compatibleGit(remote)) return true;
    setError(
      `P2P остановлен: Git base отличается (${config?.git_commit?.slice(0, 8) || "нет"} / ${
        remote?.git_commit?.slice(0, 8) || "нет"
      })`
    );
    return false;
  }

  function publicMetadata() {
    return {
      user_name: userName,
      actor_type: "human",
      git_commit: config?.git_commit || "",
      base_document_hash: config?.base_document_hash || "",
      document_hash: config?.document_hash || "",
      crdt_epoch: config?.crdt_epoch || "",
      lan_ip: config?.lan_ip || "",
    };
  }

  function sendSync(channel) {
    const update = getDocumentUpdate?.();
    if (!update) return;
    sendChannel(channel, {
      type: "sync",
      update: bytesToBase64(update),
      metadata: publicMetadata(),
    });
  }

  function sendRelaySync(remotePeerId) {
    const update = getDocumentUpdate?.();
    if (!update || !config?.crdt_epoch) return false;
    const payload = {
      type: "sync",
      update: bytesToBase64(update),
      metadata: publicMetadata(),
    };
    const sent = JSON.stringify(relayEnvelope(remotePeerId, payload)).length > RELAY_LIMIT
      ? sendChunkedSync(remotePeerId, payload)
      : sendRelay(remotePeerId, payload);
    if (sent) crdtPendingPeers.add(remotePeerId);
    return sent;
  }

  function sendChunkedSync(remotePeerId, payload) {
    const encoded = String(payload.update || "");
    if (!encoded) return false;
    const id = `${peerId}-sync-${Date.now()}`;
    const size = 24000;
    const n = Math.ceil(encoded.length / size);
    for (let i = 0; i < n; i += 1) {
      if (!sendRelay(remotePeerId, {
        type: "sync_chunk",
        id,
        i,
        n,
        update: encoded.slice(i * size, i * size + size),
        metadata: payload.metadata,
      })) return false;
    }
    return true;
  }

  function adoptSyncChunk(fromPeer, message) {
    const id = String(message.id || "");
    const n = Number(message.n) || 0;
    const i = Number(message.i);
    if (!id || !n || !Number.isFinite(i) || i < 0 || i >= n) return;
    const key = `${fromPeer}:${id}`;
    const rec = syncChunks.get(key) || {
      parts: Array(n).fill(null),
      metadata: message.metadata || {},
    };
    rec.parts[i] = String(message.update || "");
    syncChunks.set(key, rec);
    if (rec.parts.some((part) => part == null)) return;
    syncChunks.delete(key);
    handleSync(fromPeer, {
      type: "sync",
      update: rec.parts.join(""),
      metadata: rec.metadata,
    });
  }

  function sendChunkedUpdate(remotePeerId, payload) {
    const encoded = String(payload.update || "");
    if (!encoded) return false;
    const id = `${peerId}-update-${payload.id || Date.now()}`;
    const size = 24000;
    const n = Math.ceil(encoded.length / size);
    for (let i = 0; i < n; i += 1) {
      if (!sendRelay(remotePeerId, {
        type: "update_chunk",
        id,
        i,
        n,
        crdt_epoch: payload.crdt_epoch,
        update: encoded.slice(i * size, i * size + size),
      })) return false;
    }
    return true;
  }

  function adoptUpdateChunk(fromPeer, message) {
    const id = String(message.id || "");
    const n = Number(message.n) || 0;
    const i = Number(message.i);
    if (!id || !n || !Number.isFinite(i) || i < 0 || i >= n) return;
    const key = `${fromPeer}:${id}`;
    const rec = updateChunks.get(key) || {
      parts: Array(n).fill(null),
      crdt_epoch: String(message.crdt_epoch || ""),
    };
    rec.parts[i] = String(message.update || "");
    updateChunks.set(key, rec);
    if (rec.parts.some((part) => part == null)) return;
    updateChunks.delete(key);
    handleRemoteUpdate(base64ToBytes(rec.parts.join("")), rec.crdt_epoch);
    if (rec.crdt_epoch === config?.crdt_epoch) crdtPeers.add(fromPeer);
  }

  function markCrdtReady(remotePeerId) {
    if (!remotePeerId || !relayPeers.has(remotePeerId)) return;
    crdtPeers.add(remotePeerId);
    crdtPendingPeers.delete(remotePeerId);
    forcedResync.delete(remotePeerId);
    sendRelay(remotePeerId, {
      type: "crdt_ready",
      crdt_epoch: config?.crdt_epoch || "",
    });
    emitStatus();
  }

  function usesCrdtTransport(remotePeerId) {
    return (
      crdtPeers.has(remotePeerId) ||
      crdtPendingPeers.has(remotePeerId) ||
      (Boolean(adoptingEpoch) && remotePeerId === adoptingPeerId)
    );
  }

  function handleRemoteUpdate(bytes, epoch) {
    if (adoptingEpoch) {
      queuedUpdates.push({ bytes, epoch });
      return;
    }
    const id = rememberUpdate(bytes);
    if (!id) return;
    if (epoch !== config?.crdt_epoch) {
      setError("P2P update отклонён: CRDT history ещё не синхронизирована");
      return;
    }
    applyRemoteUpdate?.(bytes);
  }

  function handleSync(fromPeer, message) {
    const remote = message.metadata || remoteMetadata.get(fromPeer) || {};
    remoteMetadata.set(fromPeer, remote);
    if (!validatePeer(remote)) return;
    const bytes = base64ToBytes(String(message.update || ""));
    const remoteEpoch = String(remote.crdt_epoch || "");
    if (!remoteEpoch) {
      setError("P2P peer не прислал CRDT epoch");
      return;
    }
    if (remoteEpoch === config?.crdt_epoch) {
      handleRemoteUpdate(bytes, remoteEpoch);
      markCrdtReady(fromPeer);
      return;
    }
    if (fromPeer !== authorityPeerId) return;
    if (adoptingEpoch === remoteEpoch) return;
    const sameDocument =
      Boolean(config?.document_hash) &&
      config?.document_hash === remote.document_hash;
    const localIsClean =
      sameDocument ||
      (!config?.local_dirty && config?.document_hash === config?.base_document_hash);
    if (!localIsClean) {
      setError("P2P остановлен: локальный main.tex отличается от Git base");
      return;
    }
    adoptingEpoch = remoteEpoch;
    adoptingPeerId = fromPeer;
    adoptRemoteState?.(bytes, {
      crdt_epoch: remoteEpoch,
      expected_hash: String(remote.document_hash || ""),
    });
  }

  function handleChannelMessage(fromPeer, event) {
    let message;
    try {
      message = JSON.parse(event.data);
    } catch {
      return;
    }
    if (message.type === "hello") {
      remoteMetadata.set(fromPeer, message.metadata || {});
      if (!relayOnly() && !validatePeer(message.metadata || {})) return;
      if (Array.isArray(message.comments) || Array.isArray(message.deleted_ids)) {
        onComments?.({
          comments: Array.isArray(message.comments) ? message.comments : [],
          deleted_ids: Array.isArray(message.deleted_ids) ? message.deleted_ids : [],
        });
      }
      if (typeof message.text === "string") {
        adoptRemoteText(message.text, fromPeer, message.seq, message);
      }
      sendCommentsTo(fromPeer);
      if (relayPeers.has(fromPeer)) {
        const remote = message.metadata || {};
        const canSyncCrdt =
          compatibleGit(remote) && Boolean(remote.crdt_epoch) && Boolean(config?.crdt_epoch);
        if (canSyncCrdt) {
          if (peerId === authorityPeerId) sendRelaySync(fromPeer);
        } else if (!config?.publish_snapshot) {
          requestResync(fromPeer);
        }
        return;
      }
      if (config?.crdt_epoch === message.metadata?.crdt_epoch || peerId === authorityPeerId) {
        sendSync(connections.get(fromPeer)?.channel);
      }
      return;
    }
    if (message.type === "sync") {
      handleSync(fromPeer, message);
      return;
    }
    if (message.type === "sync_chunk") {
      adoptSyncChunk(fromPeer, message);
      return;
    }
    if (message.type === "update") {
      const epoch = String(message.crdt_epoch || "");
      handleRemoteUpdate(base64ToBytes(String(message.update || "")), epoch);
      if (epoch === config?.crdt_epoch) crdtPeers.add(fromPeer);
      return;
    }
    if (message.type === "update_chunk") {
      adoptUpdateChunk(fromPeer, message);
      return;
    }
    if (message.type === "crdt_ready") {
      if (String(message.crdt_epoch || "") === config?.crdt_epoch) {
        crdtPeers.add(fromPeer);
        crdtPendingPeers.delete(fromPeer);
        forcedResync.delete(fromPeer);
        emitStatus();
      }
      return;
    }
    if (message.type === "presence") onPresence?.(message.presence || {});
    if (message.type === "comments") {
      onComments?.({
        comments: Array.isArray(message.comments) ? message.comments : [],
        deleted_ids: Array.isArray(message.deleted_ids) ? message.deleted_ids : [],
      });
    }
    if (message.type === "tex") {
      if (usesCrdtTransport(fromPeer)) return;
      if (isStaleTex(fromPeer, message.seq, { allowEqual: true })) return;
      adoptRemoteText(message.text, fromPeer, message.seq, message);
    }
    if (message.type === "tex_chunk") {
      if (usesCrdtTransport(fromPeer)) return;
      adoptChunk(fromPeer, message);
    }
    if (message.type === "tex_span") {
      if (usesCrdtTransport(fromPeer)) return;
      if (isStaleTex(fromPeer, message.seq)) return;
      const expected = Number(message.base_len);
      const current = getText?.()?.length ?? 0;
      if (message.base_len != null && Number.isFinite(expected) && expected !== current) {
        requestResync(fromPeer, { adopt: true });
        return;
      }
      const ok = applyRemoteSpan?.({
        start: Number(message.start) || 0,
        delete_len: Number(message.delete_len) || 0,
        new_text: String(message.new_text || ""),
        pre: String(message.pre || ""),
      });
      if (ok === false) {
        requestResync(fromPeer, { adopt: true });
        return;
      }
      noteRemoteSeq(fromPeer, message.seq);
    }
    if (message.type === "tex_resync") {
      sendTexTo(fromPeer, { force: true });
    }
  }

  function attachChannel(remotePeerId, channel) {
    const entry = connections.get(remotePeerId);
    if (!entry) return;
    entry.channel = channel;
    channel.addEventListener("open", () => {
      if (stallTimer) clearTimeout(stallTimer);
      networkError = "";
      sendChannel(channel, { type: "hello", metadata: publicMetadata() });
      sendCommentsOn(channel);
      if (peerId === authorityPeerId) sendSync(channel);
      emitStatus();
    });
    channel.addEventListener("message", (event) => handleChannelMessage(remotePeerId, event));
    channel.addEventListener("close", emitStatus);
    channel.addEventListener("error", () => setError("Ошибка WebRTC DataChannel"));
  }

  function createConnection(remotePeerId, initiator = false) {
    const existing = connections.get(remotePeerId);
    if (existing) return existing.pc;
    const pc = new RTCPeerConnection({ iceServers: config?.ice_servers || [] });
    const entry = { pc, channel: null };
    connections.set(remotePeerId, entry);
    pc.addEventListener("icecandidate", (event) => {
      if (!event.candidate) return;
      publishIceCandidate(remotePeerId, event.candidate.toJSON());
    });
    pc.addEventListener("iceconnectionstatechange", () => {
      if (pc.iceConnectionState === "failed") startRelay(remotePeerId);
    });
    pc.addEventListener("connectionstatechange", () => {
      if (["failed", "closed"].includes(pc.connectionState)) {
        if (pc.connectionState === "failed") startRelay(remotePeerId);
        entry.channel?.close();
        pc.close();
        connections.delete(remotePeerId);
      }
      emitStatus();
    });
    pc.addEventListener("datachannel", (event) => attachChannel(remotePeerId, event.channel));
    if (initiator) {
      attachChannel(remotePeerId, pc.createDataChannel("researchos-yjs", { ordered: true }));
    }
    return pc;
  }

  async function offer(remotePeerId) {
    const remote = remoteMetadata.get(remotePeerId);
    if (remote && !validatePeer(remote)) return;
    const pc = createConnection(remotePeerId, true);
    const description = await pc.createOffer();
    await pc.setLocalDescription(description);
    sendSignal({
      type: "offer",
      to: remotePeerId,
      payload: { sdp: pc.localDescription },
    });
  }

  async function handleSignal(message) {
    if (message.type === "room_state") {
      if (networkError.startsWith("Signaling")) networkError = "";
      authorityPeerId = String(message.authority_peer_id || peerId);
      for (const peer of message.peers || []) {
        remoteMetadata.set(peer.peer_id, peer);
        await connectToPeer(peer.peer_id, { force: true });
      }
      armStallWatch();
      emitStatus();
      return;
    }
    if (message.type === "peer_joined") {
      authorityPeerId = String(message.authority_peer_id || authorityPeerId);
      const peer = message.peer || {};
      remoteMetadata.set(peer.peer_id, peer);
      await connectToPeer(peer.peer_id);
      armStallWatch();
      emitStatus();
      return;
    }
    if (message.type === "peer_left") {
      const remotePeerId = String(message.peer_id || "");
      connections.get(remotePeerId)?.pc?.close();
      connections.delete(remotePeerId);
      remoteMetadata.delete(remotePeerId);
      relayPeers.delete(remotePeerId);
      crdtPeers.delete(remotePeerId);
      crdtPendingPeers.delete(remotePeerId);
      lastTexSeq.delete(remotePeerId);
      resyncAt.delete(remotePeerId);
      lastTexSent.delete(remotePeerId);
      forcedResync.delete(remotePeerId);
      for (const key of [...texChunks.keys()]) {
        if (key.startsWith(`${remotePeerId}:`)) texChunks.delete(key);
      }
      for (const key of [...syncChunks.keys()]) {
        if (key.startsWith(`${remotePeerId}:`)) syncChunks.delete(key);
      }
      for (const key of [...updateChunks.keys()]) {
        if (key.startsWith(`${remotePeerId}:`)) updateChunks.delete(key);
      }
      emitStatus();
      return;
    }
    if (message.type === "offer") {
      if (relayOnly()) {
        startRelay(String(message.from || ""));
        return;
      }
      const remotePeerId = String(message.from || "");
      const remote = remoteMetadata.get(remotePeerId);
      if (remote && !validatePeer(remote)) return;
      const pc = createConnection(remotePeerId, false);
      await pc.setRemoteDescription(message.payload?.sdp);
      await flushIceCandidates(remotePeerId, pc);
      const answer = await pc.createAnswer();
      await pc.setLocalDescription(answer);
      sendSignal({
        type: "answer",
        to: remotePeerId,
        payload: { sdp: pc.localDescription },
      });
      return;
    }
    if (message.type === "answer") {
      if (relayOnly()) return;
      const remotePeerId = String(message.from || "");
      const pc = connections.get(remotePeerId)?.pc;
      if (!pc) return;
      await pc.setRemoteDescription(message.payload?.sdp);
      await flushIceCandidates(remotePeerId, pc);
      return;
    }
    if (message.type === "ice_candidate") {
      if (relayOnly()) return;
      await addRemoteIceCandidate(
        String(message.from || ""),
        message.payload?.candidate
      );
      return;
    }
    if (message.type === "relay") {
      handleRelayPayload(String(message.from || ""), message.payload || {});
      return;
    }
    if (message.type === "error") {
      const code = String(message.code || "");
      if (code === "not_joined") {
        sendJoin();
        return;
      }
      if (code === "peer_not_found") {
        return;
      }
      setError(`Signaling: ${code || "ошибка"}`);
    }
  }

  let joinAt = 0;
  function sendJoin() {
    if (signal?.readyState !== WebSocket.OPEN || !config) return;
    const now = Date.now();
    if (now - joinAt < 2000) return;
    joinAt = now;
    sendSignal({
      type: "join",
      token: config.token,
      room_id: config.room_id,
      peer_id: peerId,
      metadata: publicMetadata(),
    });
  }

  async function openSignal() {
    if (!config?.enabled || closing) return;
    if (signal?.readyState === WebSocket.OPEN) {
      sendJoin();
      return;
    }
    if (signal?.readyState === WebSocket.CONNECTING) return;
    if (refreshConfig) {
      try {
        const next = await refreshConfig();
        if (next) config = { ...config, ...next };
      } catch (error) {
        setError(error?.message || "Не удалось обновить P2P token");
      }
    }
    const ws = new WebSocket(config.signaling_url);
    signal = ws;
    ws.addEventListener("open", () => {
      joinAt = 0;
      sendJoin();
      if (heartbeat) clearInterval(heartbeat);
      heartbeat = setInterval(() => sendSignal({ type: "heartbeat" }), 15000);
      emitStatus();
    });
    ws.addEventListener("message", (event) => {
      try {
        void handleSignal(JSON.parse(event.data));
      } catch (error) {
        setError(error?.message || "Некорректный signaling message");
      }
    });
    ws.addEventListener("close", (event) => {
      if (heartbeat) clearInterval(heartbeat);
      heartbeat = null;
      if (signal === ws) signal = null;
      forgetRemotePeers();
      joinAt = 0;
      if (!closing) {
        if (event.code === 1008) {
          setError(`Signaling отклонил join (${event.reason || `код ${event.code}`})`);
        }
        if (reconnectTimer) clearTimeout(reconnectTimer);
        reconnectTimer = setTimeout(() => void openSignal(), 1500);
      }
      emitStatus();
    });
    ws.addEventListener("error", () => setError("Signaling недоступен"));
  }

  if (typeof document !== "undefined") {
    document.addEventListener("visibilitychange", () => {
      if (document.visibilityState === "visible") wakeSignal();
    });
  }
  if (typeof window !== "undefined") {
    window.addEventListener("pageshow", () => wakeSignal());
    window.addEventListener("online", () => wakeSignal());
  }

  async function connect(nextConfig) {
    disconnect();
    config = { ...nextConfig };
    closing = false;
    networkError = "";
    if (config.enabled) await openSignal();
    emitStatus();
  }

  function disconnect() {
    closing = true;
    if (heartbeat) clearInterval(heartbeat);
    if (reconnectTimer) clearTimeout(reconnectTimer);
    if (stallTimer) clearTimeout(stallTimer);
    if (texBackupTimer) clearTimeout(texBackupTimer);
    heartbeat = null;
    reconnectTimer = null;
    texBackupTimer = null;
    for (const { pc, channel } of connections.values()) {
      channel?.close();
      pc.close();
    }
    connections.clear();
    remoteMetadata.clear();
    pendingIceCandidates.clear();
    queuedUpdates.length = 0;
    queuedLocalSpans.length = 0;
    queuedLocalSnapshot = "";
    adoptingEpoch = "";
    adoptingPeerId = "";
    relayPeers.clear();
    crdtPeers.clear();
    crdtPendingPeers.clear();
    lastTexSeq.clear();
    resyncAt.clear();
    lastTexSent.clear();
    forcedResync.clear();
    needSnapshot.clear();
    typedAt = 0;
    texChunks.clear();
    syncChunks.clear();
    updateChunks.clear();
    localTexSeq = 0;
    if (signal?.readyState === WebSocket.OPEN) sendSignal({ type: "leave" });
    signal?.close();
    signal = null;
    emitStatus();
  }

  function broadcastUpdate(update) {
    const id = rememberUpdate(update);
    if (!id || !config?.crdt_epoch) return;
    const payload = {
      type: "update",
      id,
      crdt_epoch: config.crdt_epoch,
      update: bytesToBase64(update),
    };
    for (const { channel } of connections.values()) sendChannel(channel, payload);
    for (const remotePeerId of relayPeers) {
      if (crdtPeers.has(remotePeerId) || crdtPendingPeers.has(remotePeerId)) {
        if (JSON.stringify(relayEnvelope(remotePeerId, payload)).length > RELAY_LIMIT) {
          sendChunkedUpdate(remotePeerId, payload);
        } else {
          sendRelay(remotePeerId, payload);
        }
      }
    }
  }

  function broadcastPresence(presence) {
    const payload = { type: "presence", presence: { peer_id: peerId, ...presence } };
    for (const { channel } of connections.values()) sendChannel(channel, payload);
    for (const remotePeerId of relayPeers) sendRelay(remotePeerId, payload);
  }

  function noteLocalState(metadata) {
    const completedAdoption =
      Boolean(adoptingEpoch) && String(metadata?.crdt_epoch || "") === adoptingEpoch;
    config = { ...config, ...metadata };
    if (completedAdoption) {
      config.local_dirty = false;
      config.publish_snapshot = false;
      adoptingEpoch = "";
      const adoptedFrom = adoptingPeerId;
      adoptingPeerId = "";
      markCrdtReady(adoptedFrom);
      const queued = queuedUpdates.splice(0);
      for (const item of queued) handleRemoteUpdate(item.bytes, item.epoch);
      if (queuedLocalSnapshot) {
        const text = queuedLocalSnapshot;
        queuedLocalSnapshot = "";
        queuedLocalSpans.length = 0;
        reapplyLocalText?.(text);
      } else {
        const spans = queuedLocalSpans.splice(0);
        for (const span of spans) reapplyLocalSpan?.(span);
      }
      networkError = "";
    }
    emitStatus();
  }

  return {
    connect,
    disconnect,
    broadcastUpdate,
    broadcastTex,
    requestTexFromPeers,
    broadcastTexSpan,
    broadcastPresence,
    broadcastComments,
    noteLocalState,
    markLocalDirty: () => {
      config = { ...config, local_dirty: true };
      scheduleTexBackup();
    },
    noteLocalTyped: () => {
      typedAt = Date.now();
      config = { ...config, local_dirty: true };
      scheduleTexBackup();
    },
    markPublishSnapshot: () => {
      config = { ...config, local_dirty: true, publish_snapshot: true };
    },
  };
}
