# Paper collaboration — Spike B

Spike B connects browser Yjs documents from separate ResearcherOS instances
through a full-mesh WebRTC network (maximum five peers). The cloud component
only routes WebRTC SDP and ICE messages; document updates use encrypted
DataChannels.

## Signaling service

Run locally:

```bash
export KOI_COLLAB_TOKEN_SECRET="$(openssl rand -hex 32)"
./.venv/bin/uvicorn koi.paper.collaboration.signaling_service:app \
  --host 0.0.0.0 --port 8090
```

Yandex API Gateway does **not** proxy a raw uvicorn WebSocket. The container
receives `CONNECT` / `MESSAGE` / `DISCONNECT` as HTTP on `/signal` (the
client path; container `path:` rewrite is ignored) and sends frames back
through the WebSocket Connections API. Rooms stay in memory on **one** warm
replica (`--min-instances 1`). A gateway message is at most 128 KB; oversized
CRDT syncs must stay on DataChannel or be split later.

```bash
# same KOI_COLLAB_TOKEN_SECRET as both ResearcherOS machines
./deploy/signaling/deploy.sh
```

Then set `KOI_COLLAB_SIGNALING_URL=wss://<gateway-domain>/signal` on both
machines and restart KOI. Horizontal scaling still needs a shared room store.

Every ResearcherOS instance must use the same secret and endpoint:

```dotenv
KOI_COLLAB_SIGNALING_URL=wss://<signaling-host>/signal
KOI_COLLAB_TOKEN_SECRET=<same-random-secret>
KOI_COLLAB_STUN_URL=stun:stun.l.google.com:19302
KOI_COLLAB_TURN_URL=turns:<turn-host>:5349
KOI_COLLAB_TURN_USERNAME=<temporary-user>
KOI_COLLAB_TURN_CREDENTIAL=<temporary-password>
```

Restart ResearcherOS after changing `.env`.

## One-Mac disposable test

The test runner creates two temporary Git clones, starts two isolated
ResearcherOS APIs and browsers, checks concurrent edits and reconnect, verifies
both `main.tex` files, then removes every temporary process and directory:

```bash
./.venv/bin/python scripts/test-paper-p2p.py \
  --project talking-heads \
  --slug emnlp_talking_heads
```

If Chromium is not installed yet:

```bash
./.venv/bin/playwright install chromium
```

## Safety boundary

- The room ID uses the normalized Git remote, paper slug, and relative path.
- Signaling accepts short-lived HS256 room tokens minted by local ResearcherOS.
- Peers with different `HEAD` commits are shown as incompatible and never
  exchange document updates.
- Independently seeded Yjs documents are not merged directly because that
  duplicates their initial text. A clean joining peer adopts the first peer's
  CRDT history. A joining peer with local changes is blocked instead.
- Git remains the durable checkpoint; WebRTC does not create commits.
- If ICE fails (VPN/firewall), peers fall back to opaque `relay` frames on
  the signaling socket so the same room can still edit. Prefer DataChannel
  when it opens.

## Two-instance acceptance checklist

1. Clone the same repository twice and ensure both clones are on the same
   commit.
2. Start ResearcherOS in both clones with distinct local ports and identical
   collaboration environment variables.
3. Open the same paper. Both headers should change from `P2P · waiting` to
   `P2P · 2`.
4. Type in Alice. Bob should update without a filesystem save or Git operation.
5. Type concurrently in both browsers. After activity stops, compare
   `main.tex`; both files should be identical and dirty in Git.
6. Stop Bob, edit in Alice, then reopen Bob. Bob should adopt the current room
   state and converge.
7. Put Bob on another Git commit. The UI should show `P2P stopped: Git base
   differs`, and neither document should be changed.
8. Make an unsaved local edit in Bob before initial sync. Bob must report that
   local `main.tex` differs rather than silently replacing or merging it.
9. Test once with TURN disabled and once from networks that require the
   configured TURN relay.
