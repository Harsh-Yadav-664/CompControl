# CompControl — Autonomous Desktop Command Center

CompControl is a fast, lightweight Windows 11 desktop command center that executes natural-language PC requests, media workflows, native software installations (`winget`), and AI-interpreted actions with **1-click Auto-Approve** for safe operations and a multi-layer **Exploit Shield** for security.

```text
+-------------------------------------------------------------------+
| COMPCONTROL // AUTONOMOUS COMMAND CENTER    [READY]  [x] 1-Click  |
+-------------------------------------------------------------------+
| Browser: [Default v]  [Run]  [Ask AI]  [Apps]  [AI Setup]         |
| [ > play my liked songs list / install vlc / open vscode...     ] |
|                                                                   |
| Quick Actions: [Spotify] [Liked Songs] [YouTube] [VS Code] [Sys]  |
|                                                                   |
| COMMAND OUTPUT & EXECUTION STREAM                                 |
| Open Spotify Liked Songs [EXECUTED]                               |
| Action: liked  Target: spotify (spotify:collection:tracks)        |
+-------------------------------------------------------------------+
```

## Key Capabilities

- **1-Click Autonomous Execution (Auto-Approve ON by default):** Safe everyday actions (opening apps, playing Spotify Liked Songs, searching YouTube/Google/Maps/Spotify, media keys, system telemetry, opening known folders, and installing verified `winget` packages) execute immediately on **Enter**, **Run**, or **Ask AI** without repetitive confirmation popups.
- **Natural Intent & AI Routing:** Handles natural phrases such as *"play my liked songs list"*, *"open Spotify and play my liked playlist"*, *"open yt and search for Sidemen videos"*, *"install VLC"*, *"open Visual Studio Code"*, *"system info"*, and *"open downloads"*.
- **Autonomous App Discovery (`launch_app`):** Automatically scans Windows `Get-StartApps` in the background and searches known installation paths (`Program Files`, `LocalAppData\Programs`, `PATH`) so requesting an installed app launches it directly without manual multi-window pickers.
- **Native Software Installation (`winget_install`):** Installs software natively via Windows Package Manager (`winget install --id <Package> -e --accept-source-agreements --accept-package-agreements`) with built-in resolution for 35+ popular packages (`VLC`, `Blender`, `VS Code`, `Discord`, `OBS`, `Git`, `Python`, `7-Zip`, `PowerToys`, etc.).
- **Unleashed AI Planner + Exploit Shield:** Supports cloud (Groq, Gemini, OpenAI, Custom HTTPS) and local (Ollama) models. The AI can propose app launches, `winget` installations, system controls, folder navigation, PowerShell commands, and Python snippets.
- **Zero-Bloat Native UI:** Built with Python 3.11+ standard library and dark Cyber-Obsidian Tkinter HUD — zero third-party runtime dependencies and minimal RAM/CPU footprint.

## Security & Privacy Architecture (Exploit Shield)

CompControl eliminates confirmation fatigue for safe tasks while maintaining strict defense-in-depth against exploitation:

1. **Exploit Shield (`compcontrol/consent.py`):** Blocks obfuscated/encoded commands (`-EncodedCommand`), remote script download cradles (`Invoke-Expression`, `DownloadString`, `iwr | iex`), `mshta`/`regsvr32`/`rundll32`/`certutil`/`bitsadmin` LOLBins, SAM/LSASS/credential dumping, firewall/Defender tampering, and SSH/cloud key exfiltration (`Blocked by CompControl Exploit Shield`).
2. **Tiered Risk Gate:**
   - **Safe & Standard Tasks:** Auto-approved and executed immediately when `1-Click Auto-Approve` is active.
   - **High-Impact / Destructive Commands:** Commands that delete files (`Remove-Item`, `del`), kill processes (`Stop-Process`, `taskkill`), format/partition disks, edit registry keys, or shut down/restart the PC always trigger a topmost native Windows confirmation dialog with a 1-second focus-steal guard.
3. **Loopback & Origin Protection:** The optional `--web` interface binds strictly to `127.0.0.1`, requires a per-process cryptographic token (`X-CompControl-Token`), and validates `Host`, `Origin`, and `Sec-Fetch-Site` headers to prevent browser/CSRF/DNS-rebinding attacks.
4. **Private AI Key Storage:** API keys are never written to logs or command histories. If you opt into *"Remember AI config on this PC"*, settings are saved to `~/.compcontrol_ai.json` with owner-only (`0600`) file permissions.

## Running on Windows 11

```powershell
py -3 -m compcontrol
```

Or double-click `run_compcontrol.cmd` (or `run_compcontrol_widget.cmd` for compact HUD mode).

### Modes

| Mode | Command | Behavior |
|---|---|---|
| Native desktop HUD (default) | `py -3 -m compcontrol` | Launches the native dark Command Center window (`Ctrl+Alt+Space` global hotkey). |
| Compact widget | `py -3 -m compcontrol --widget` | Starts the native window in compact HUD mode. |
| Interactive CLI | `py -3 -m compcontrol --cli` | Terminal prompt that auto-executes safe plans and prompts `APPROVE` only for high-impact actions. |
| Demo / non-Windows preview | `py -3 -m compcontrol --demo` | Simulates actions without launching Windows processes. |
| Local web preview | `py -3 -m compcontrol --web --demo` | Loopback web UI on `http://127.0.0.1:8765`. |

## Verification

```bash
python3 -m unittest discover -s tests -v
python3 -m compileall -q compcontrol scripts tests
```
