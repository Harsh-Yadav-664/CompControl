# CompControl

**A local-first desktop assistant, built around explicit user control.** CompControl starts with a small Windows-friendly command runner; voice, AI providers, browser automation, and Android are future work—not capabilities of this prototype.

## Current prototype

- Python 3.10+; standard library only.
- `help`, `time`, and `open calculator` are the only supported commands.
- Calculator is launched by a fixed Windows executable name; user input is never passed to a shell or used to construct executable arguments.
- Unknown commands are rejected. No network calls, telemetry, API keys, or saved command history.

### Run

```powershell
py -3 -m compcontrol
py -3 -m unittest discover -s tests -v
```

Calculator launch is Windows-only. On other platforms, the command returns an explanatory message. The parser and time command work cross-platform.

## Design direction

Keep the core a small, typed, deterministic intent router. A future desktop UI can call the same core; a future Android companion should talk to an explicitly paired desktop service over authenticated TLS, not expose a listening endpoint by default. Provider adapters should be opt-in and capability-limited: local model first (e.g. Ollama or an OpenAI-compatible local endpoint), with user-configured paid providers later. Provider secrets belong in the OS credential store and must never enter prompts, logs, or source control.

Suggested progression: (1) safe intent registry and tests, (2) Windows UI and explicit permission settings, (3) browser/media integrations through documented APIs and user-confirmed actions, (4) optional local speech, (5) paired Android remote-control client. Treat webpages and model output as untrusted input; neither can grant permissions or bypass the action policy.

## Safety boundaries

This prototype does not control arbitrary files, run commands, install software, or browse the web. It is not a security guarantee. Any future action that changes state, sends data, or accesses personal content needs a narrow capability, clear preview, and explicit confirmation. Remote access should remain disabled until pairing, authentication, authorization, TLS, replay protection, and audit behavior are designed and reviewed.

Never paste access tokens into chat, issues, or source files. If a token is exposed, revoke it immediately in the provider's security settings and review recent activity; removing the message alone is not sufficient.

See [docs/architecture.md](docs/architecture.md) and [docs/threat-model.md](docs/threat-model.md).
