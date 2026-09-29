# Architecture · native desktop incremental assistant

## Primary flow

```text
Native Tk window → offline planner ───────────────────────────────┐
       │                                                        │
       └→ user-approved AI disclosure → provider (worker thread) │
                 → strict JSON proposal parser → local summary ─┤
                                                                ▼
                            Broker: immutable plan / expiring one-use approval
                                                                │
                                     native confirmation (Tk main thread)
                                                                │
                                     validity check at dispatch → WindowsExecutor
```

Default `python -m compcontrol` opens `desktop.py`; it does not start `server.py` or a browser. The optional `--web` interface remains for diagnostics/demo, with text-only chat. CLI uses offline skills and the same broker/executor. No mode executes arbitrary model text.

## AI interpretation boundary

`TextProvider.propose()` sends a single approved request plus a fixed capability schema. Local Ollama uses JSON mode; OpenAI-compatible APIs receive the schema in the system prompt without assuming vendor-specific tool APIs. `ai_planner.parse_proposal()` rejects extra/duplicate keys, action arrays, arbitrary code/invented URLs, unsupported targets, malformed types, oversized or hidden-control-bearing text. Action summaries are generated locally, not taken from model prose. A message-only response has no action path. `actions.validate()` runs again in the broker and executor.

Network I/O runs in a daemon worker, which only puts results into a queue. All widgets and parented consent windows stay on the Tk thread. An application revision discards late UI results; a separate broker-issued, one-use, expiring interpretation ticket prevents a late model response from creating a valid approval after a new request, edit, Pause, Cancel or Clear. Already-sent network traffic cannot be recalled; no automatic retry occurs.

Planning is distinct from authority. Even a schema-valid model proposal can misunderstand intent. The user reviews exact action, destination and browser, then confirms in a separate native dialog. No automatic multi-step execution or blanket permission. Failures consume approval; they do not retry.

## Desktop and lightweight scope

Python's Tcl/Tk window, slate/violet palette, optional compact layout and topmost toggle. A Windows `RegisterHotKey` message thread receives only Ctrl+Alt+Space activation, not text or keystroke history; a queue marshals summons onto Tk. Conflicting registration is reported, and the app remains accessible on the taskbar. Closing exits and unregisters the shortcut. No startup/tray agent, inference engine, browser runtime or network listener is bundled. Lightweight is an architectural aim, not a benchmark claim.

Provider settings entered in the native app live only in process memory; environment defaults remain supported. Jarvis/Friday share permissions. Read-only exact destinations support copy/review. Activity is a bounded 60-event in-memory label/status ring, without raw requests or query strings.

## Optional web surface

`server.py` serves allowlisted assets and a bounded JSON API. Local mode enforces exact loopback Host/Origin and an in-memory bearer token (delivered in a URL fragment), CSP and native consent. Network/demo mode uses a no-op executor and disables all providers. Python's HTTP server is not production internet infrastructure. Native use does not inherit this listening surface.

## Evolving target grounding

See [broader assistant architecture](capable-assistant.md). Discovery is local-only: a scan produces ephemeral app selection handles; AI can request discovery but cannot choose the handle. Classic app shortcuts are not executed; a manually selected `.exe` is fingerprinted and rechecked before launch. HTTPS navigation is exact-request-grounded when AI proposed. Project files are user-selected; only preview/export of an exact change is currently offered, never a direct source edit. The one-effect broker and no blanket approval remain. Additional tools need their own target-identity/side-effect rules rather than an ever-growing name allowlist.

## Deferred

OS credential vault and signed distribution; measured resource/latency budget; accessible native styling refinements; optional push-to-talk; supported OAuth media control; safe direct file edits, deletes and applied patches. Android needs authenticated pairing, TLS, per-device grants, revocation and replay protection—not an exposed desktop HTTP port.
