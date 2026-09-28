# Architecture · v0.2

## Implemented

```text
CLI / local browser command center
           │ explicit user request
           ▼
Planner (offline, no I/O) → immutable typed Action → Broker
                                                  │
                               expiring single-use approval
                                                  │
                                     Native Windows consent
                                                  │
                              revalidate pause/expiry at dispatch
                                                  │
                                        WindowsExecutor

Ask AI + explicit disclosure → TextProvider → plain text only
                                 (no path to the broker)
```

`planner.py` recognizes bounded phrases; `models.py` defines immutable contracts; `actions.py` validates again at the OS boundary. `broker.py` serializes execution, consumes approval before dispatch, and revokes pending/waiting work on pause or clear. Failures are not automatically retried. Native consent defaults to denial and expires with the request. Once a dispatch is committed, pause cannot recall it.

`server.py` serves allowlisted static assets and a small JSON API. The local token arrives via a URL fragment, is removed from the address bar, and is kept only in JavaScript memory. No credentials in cookies or browser storage. Local mode enforces exact loopback Host and Origin plus bearer authentication; external demo mode has a physically separate no-op executor and disabled AI. Preview sessions are shared, public, in-memory simulations, not remote desktop sessions.

API: `GET /api/state`; `POST /api/plan`, `/api/confirm`, `/api/cancel`, `/api/pause`, `/api/clear`, `/api/chat`. Confirm accepts only a server-issued approval ID, never a client action body. No permissive CORS. JSON request/response bounds and provider timeouts apply. Activity is a 60-event memory ring with labels/outcomes only.

## Technology decision

Python standard library + static HTML/CSS/JS keeps this source prototype dependency-free and easy to audit. Windows Python includes Tk for the independent consent window. The existing browser supplies rendering, avoiding a bundled Chromium runtime. This supersedes the earlier provisional Tk-only chat / .NET suggestion; benchmark before choosing a long-term native shell. Python's HTTP server is **not an internet-facing production server**.

Jarvis and Friday are presentation/persona choices on one capability engine, not two permission-bearing agents. AI is opt-in, single-turn and text-only. Ollama uses loopback HTTP; OpenAI-compatible providers require HTTPS. Redirects and environment HTTP proxies are disabled to avoid credential forwarding. Secrets come from the process launch environment; a credential-manager backend remains future work.

## Deferred

Local speech recognition/TTS loaded on demand; OAuth-backed Spotify integration if account/API eligibility allows; richer bounded skills; signed Windows distribution. Android must be a paired client with authenticated TLS, scoped per-device grants, revocation and replay defense—not an open desktop HTTP port. No third-party plugin execution until isolation and review rules exist.
