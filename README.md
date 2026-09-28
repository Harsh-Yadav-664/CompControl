# CompControl · Jarvis + Friday

A Windows-first personal command center: deterministic skills, visible plans, one-use approvals, and optional text-only AI. **An early working prototype, not an unrestricted autonomous agent.**

## Start on Windows

Install **64-bit Python 3.10+** from python.org with Tcl/Tk enabled, download this repository, and open PowerShell in its folder:

```powershell
py -3 -m compcontrol
```

Your browser opens the local command center. Keep the terminal open. Every desktop effect requires approval in the command center **and a native Windows dialog**. Closing the dialog denies the action. Ctrl+C stops the service. No administrator access is required.

```powershell
py -3 -m compcontrol --cli       # terminal interface, same approval broker
py -3 -m compcontrol --demo      # safe simulation, no desktop actions or AI
py -3 -m unittest discover -s tests -v
```

On Linux/macOS, use `python3 -m compcontrol --demo`. Desktop control is Windows-only. The browser demo cannot control your laptop.

## Try these

| Request | Actual behavior after approval |
|---|---|
| `open calculator` / `open Notepad` | Launches a registered Windows executable |
| `open Brave` | Opens Brave, not a silent default-browser substitution |
| `open Chrome and search for Sidemen videos on YouTube` | Opens YouTube results in Chrome |
| `open Spotify and play sad Hindi songs` | Opens Spotify search; **you select Play** |
| `open Spotify and play my liked playlist` | Opens the liked-songs web page; you sign in and start playback |
| `search Maps for coffee near Delhi` | Opens Google Maps results |
| `toggle playback` / `next track` / `volume down` | Sends one Windows media key; active player state is not read |
| `calculate (2400 * .18) + 2400` / `time` | Answers locally without a provider |

Jarvis and Friday have separate presentation styles but the **same permissions**. Shortcuts are editable and only prepare commands. New requests invalidate previous approvals. Pause clears pending approval and revokes a waiting native dialog; it cannot undo an action already dispatched.

## Optional AI

AI is disabled by default and **never executes tools**. First install Ollama separately and download a model appropriate for your hardware. Then:

```powershell
$env:COMPCONTROL_PROVIDER = 'ollama'
$env:COMPCONTROL_MODEL = 'your-installed-model'
py -3 -m compcontrol
```

Select **Ask AI** and accept the per-question disclosure. Only that question is sent, not conversation history, files or activity. Local inference is optional and may use significant RAM/CPU; no model is bundled or automatically downloaded.

HTTPS OpenAI-compatible APIs are also supported:

```powershell
$env:COMPCONTROL_PROVIDER = 'openai'
$env:COMPCONTROL_BASE_URL = 'https://your-provider.example/v1'
$env:COMPCONTROL_MODEL = 'your-provider-model'
# Set COMPCONTROL_API_KEY through your trusted secret manager / launch environment.
py -3 -m compcontrol
```

Do not put actual keys in scripts, command history or source control. Keys remain in process memory/environment and are not returned to the browser or sent as prompt text. OS credential-store integration is **not implemented**. Provider processes/admins on your machine may still access environment secrets. Cloud requests may cost money and follow the provider's privacy policy. This is an OpenAI-compatible adapter, not a promise to support every API format.

## Safety and limitations

- No arbitrary shell execution, filesystem editing, deletion, account sign-in automation, purchases, scraping, plugins, telemetry or microphone capture.
- Fixed HTTPS destinations; bounded encoded queries; named apps resolved from known installation directories, never PATH or prompt-supplied executables.
- Local service binds to `127.0.0.1`, uses a random in-memory bearer token, exact Host/Origin checks, strict CSP and native action confirmation. Keep the private launch URL private. Reloading locks the local UI; reopen the launch URL from the terminal.
- Public/network binds are **demo only**, with no desktop executor and no AI provider, regardless of environment configuration.
- In-memory activity stores action labels/status, not raw queries. Browser preferences save persona, browser and shortcuts; don't put private data in shortcuts. Browser history and destination websites may retain searches.
- Standard Windows app installs are supported; unusual locations / some Store installs may fail explicitly. Native actions are dispatched, not verified as successfully loaded or played.
- No always-listening voice, screen reading, general desktop automation, Android APK, remote pairing or signed installer yet.
- This is not a guarantee against compromise or account bans. Do not run elevated, expose local mode through tunnels, or bypass provider/service rules.

## Development and packaging

Standard-library runtime; plain HTML/CSS/JS, no Node build or CDN. Uses the existing browser rather than shipping Chromium. Tk is loaded only for native consent. No measured performance claims yet.

- [Architecture](docs/architecture.md)
- [Threat model](docs/threat-model.md)
- [Research and product choices](docs/research.md)
- [Windows acceptance checklist](docs/windows-testing.md)
- [Roadmap](docs/roadmap.md)

`scripts/start-windows.cmd` launches from a source checkout. `scripts/build-windows.ps1` builds an unsigned Windows folder executable using PyInstaller. Packaging downloads build dependencies; normal runtime needs none. Do not disable Windows security to run untrusted binaries. A signed release is future work.
