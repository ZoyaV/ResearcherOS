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

export function createPaperWebRtcMesh({
  peerId,
  userName,
  getDocumentUpdate,
  applyRemoteUpdate,
  adoptRemoteState,
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
  let adoptingEpoch = "";
  let networkError = "";

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
    if (!pc.remoteDescription) {
      const queued = pendingIceCandidates.get(remotePeerId) || [];
      queued.push(candidate);
      pendingIceCandidates.set(remotePeerId, queued);
      return;
    }
    try {
      await pc.addIceCandidate(candidate);
    } catch (error) {
      setError(error?.message || "WebRTC ICE candidate rejected");
    }
  }

  function schedulePeerOffer(remotePeerId) {
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

  function emitStatus() {
    const connectedPeers = [...connections.values()].filter(
      ({ channel }) => channel?.readyState === "open"
    ).length;
    onStatus?.({
      enabled: Boolean(config?.enabled),
      signaling: signal?.readyState === WebSocket.OPEN,
      remotePeerCount: connectedPeers,
      authorityPeerId,
      error: networkError,
    });
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

  function handleRemoteUpdate(bytes, epoch) {
    const id = rememberUpdate(bytes);
    if (!id) return;
    if (adoptingEpoch) {
      queuedUpdates.push({ bytes, epoch });
      return;
    }
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
      return;
    }
    if (fromPeer !== authorityPeerId) return;
    if (adoptingEpoch === remoteEpoch) return;
    const localIsClean =
      !config?.local_dirty &&
      (config?.document_hash === config?.base_document_hash ||
        config?.document_hash === remote.document_hash);
    if (!localIsClean) {
      setError("P2P остановлен: локальный main.tex отличается от Git base");
      return;
    }
    adoptingEpoch = remoteEpoch;
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
      if (!validatePeer(message.metadata || {})) return;
      if (config?.crdt_epoch === message.metadata?.crdt_epoch || peerId === authorityPeerId) {
        sendSync(connections.get(fromPeer)?.channel);
      }
      return;
    }
    if (message.type === "sync") {
      handleSync(fromPeer, message);
      return;
    }
    if (message.type === "update") {
      handleRemoteUpdate(
        base64ToBytes(String(message.update || "")),
        String(message.crdt_epoch || "")
      );
      return;
    }
    if (message.type === "presence") onPresence?.(message.presence || {});
  }

  function attachChannel(remotePeerId, channel) {
    const entry = connections.get(remotePeerId);
    if (!entry) return;
    entry.channel = channel;
    channel.addEventListener("open", () => {
      sendChannel(channel, { type: "hello", metadata: publicMetadata() });
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
      sendSignal({
        type: "ice_candidate",
        to: remotePeerId,
        payload: { candidate: event.candidate.toJSON() },
      });
    });
    pc.addEventListener("connectionstatechange", () => {
      if (["failed", "closed"].includes(pc.connectionState)) {
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
      authorityPeerId = String(message.authority_peer_id || peerId);
      for (const peer of message.peers || []) {
        remoteMetadata.set(peer.peer_id, peer);
        if (validatePeer(peer)) {
          try {
            await offer(peer.peer_id);
            schedulePeerOffer(peer.peer_id);
          } catch (error) {
            setError(error?.message || "WebRTC offer failed");
          }
        }
      }
      emitStatus();
      return;
    }
    if (message.type === "peer_joined") {
      authorityPeerId = String(message.authority_peer_id || authorityPeerId);
      const peer = message.peer || {};
      remoteMetadata.set(peer.peer_id, peer);
      validatePeer(peer);
      emitStatus();
      return;
    }
    if (message.type === "peer_left") {
      const remotePeerId = String(message.peer_id || "");
      connections.get(remotePeerId)?.pc?.close();
      connections.delete(remotePeerId);
      remoteMetadata.delete(remotePeerId);
      emitStatus();
      return;
    }
    if (message.type === "offer") {
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
      const remotePeerId = String(message.from || "");
      const pc = connections.get(remotePeerId)?.pc;
      if (!pc) return;
      await pc.setRemoteDescription(message.payload?.sdp);
      await flushIceCandidates(remotePeerId, pc);
      return;
    }
    if (message.type === "ice_candidate") {
      await addRemoteIceCandidate(
        String(message.from || ""),
        message.payload?.candidate
      );
      return;
    }
    if (message.type === "error") {
      setError(`Signaling: ${message.code || "ошибка"}`);
    }
  }

  async function openSignal() {
    if (!config?.enabled || closing) return;
    const ws = new WebSocket(config.signaling_url);
    signal = ws;
    ws.addEventListener("open", () => {
      networkError = "";
      sendSignal({
        type: "join",
        token: config.token,
        room_id: config.room_id,
        peer_id: peerId,
        metadata: publicMetadata(),
      });
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
    ws.addEventListener("close", () => {
      if (heartbeat) clearInterval(heartbeat);
      heartbeat = null;
      signal = null;
      emitStatus();
      if (!closing) reconnectTimer = setTimeout(() => void openSignal(), 1500);
    });
    ws.addEventListener("error", () => setError("Signaling недоступен"));
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
    heartbeat = null;
    reconnectTimer = null;
    for (const { pc, channel } of connections.values()) {
      channel?.close();
      pc.close();
    }
    connections.clear();
    remoteMetadata.clear();
    pendingIceCandidates.clear();
    queuedUpdates.length = 0;
    adoptingEpoch = "";
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
  }

  function broadcastPresence(presence) {
    for (const { channel } of connections.values()) {
      sendChannel(channel, { type: "presence", presence: { peer_id: peerId, ...presence } });
    }
  }

  function noteLocalState(metadata) {
    const completedAdoption =
      Boolean(adoptingEpoch) && String(metadata?.crdt_epoch || "") === adoptingEpoch;
    config = { ...config, ...metadata };
    if (completedAdoption) {
      config.local_dirty = false;
      adoptingEpoch = "";
      const queued = queuedUpdates.splice(0);
      for (const item of queued) handleRemoteUpdate(item.bytes, item.epoch);
      networkError = "";
    }
    emitStatus();
  }

  return {
    connect,
    disconnect,
    broadcastUpdate,
    broadcastPresence,
    noteLocalState,
    markLocalDirty: () => {
      config = { ...config, local_dirty: true };
    },
  };
}
