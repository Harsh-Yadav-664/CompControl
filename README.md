# CompControl · Jarvis + Friday

A **Windows-first native desktop assistant** with a compact widget mode, local skills, optional cloud AI interpretation, and visible approval before desktop actions. App names are no longer limited to the shortcut dictionary. Early source—not yet a signed or Windows-verified release.

## Fastest path: double-click, no browser UI or Ollama

Use the supplied **CompControl-Windows-Source-0.4.0.zip**, extract it to a new folder, install standard Windows Python 3.12 with Tcl/Tk once, then double-click **Start CompControl.cmd** or **Start Widget.cmd**. The native title includes **0.4.0**. The green browser preview is the old/optional web interface, not this window.

**[Step-by-step Windows + Groq/Gemini/NVIDIA setup](docs/windows-quickstart.md)** · `Check Windows Setup.cmd` checks Python/Tk and the reported YouTube command. No pip dependencies, local model or GPU are required for this source launch.

In **AI settings**, choose **Groq (cloud)**, **Gemini (cloud)** or **NVIDIA NIM (cloud)**, paste your key, select **Test AI setup**, then **Apply for this session**. Tests use your API quota but cause no desktop effect. Model access and free limits are provider/account-dependent; there is no automatic paid fallback. Ollama remains optional, not required.

## Run on Windows

Install **64-bit Python 3.10+** from python.org with **Tcl/Tk enabled**, download/extract this repository, and open PowerShell in its folder:

```powershell
py -3 -m compcontrol
```

This opens a **native Tk window**, not a browser page. No web server, Chromium runtime, administrator privileges, third-party runtime packages, or AI model are needed for local skills.

- Double-click `scripts/start-windows.pyw` for a no-console launch (requires Python file associations).
- If it fails, run `scripts/start-windows.cmd` for diagnostics.
- Enable **Widget** for the compact layout and **Pin on top** to keep it visible.
- **Ctrl+Alt+Space** summons the running window on Windows. If another app owns the shortcut, a notice appears; use the taskbar instead.
- **Enter** in the request field prepares a plan, never approves it. **Ctrl+L** focuses the field, **Esc** cancels pending work, **Ctrl+.** pauses actions while CompControl is focused, including its native approval dialog.
- Close the window to quit. There is no hidden tray/startup service.

### First useful test

Type **`open a youtube tab and find Sidemen videos`**, then select **Plan request**. Review the search terms, browser and destination. Select **Review & approve…**, then **Allow once** in the native confirmation dialog. YouTube results open only after approval; no video is auto-selected.

| Request | Actual behavior after approval |
|---|---|
| `open yt and search for mr whose the boss` | Opens YouTube results; no AI needed |
| `open calculator` / `open Notepad` | Launches a built-in Windows shortcut |
| `open Visual Studio Code` / `find installed app` | Offers local Start-menu discovery; select an exact packaged app or a trusted classic `.exe`, then approve |
| `project files` | Opens a local exact-file selector and replacement preview; reviews the full target/hash then exports a new patch after native approval **without changing the original** |
| `install Blender` / `download VLC` | Searches Google for official Windows download results; you verify/download/install manually |
| `open https://example.org/` | Opens an exact HTTPS URL after review; no installer/download management |
| `ask ChatGPT to do deep research on battery recycling` | Opens ChatGPT with a draft shown for you to copy; you start the new Deep research chat yourself |
| `open Brave` | Opens Brave, with no silent browser substitution |
| `open Chrome and search for Sidemen videos on YouTube` | Opens YouTube results in Chrome |
| `show me Sidemen videos on YouTube` | Opens YouTube search results |
| `open Spotify and play sad Hindi songs` | Uses the Spotify desktop URI handler to open search when installed; **you select Play** |
| `open Spotify and play my liked playlist` | Uses the Spotify URI handler for liked songs; sign-in/playback remain manual |
| `search Maps for coffee near Delhi` | Opens Google Maps results |
| `toggle playback` / `next track` / `volume down` | Sends one Windows media key; current player state is not read |
| `calculate (2400 * .18) + 2400` / `time` | Answers locally; no provider or approval needed |

Editing the request or browser revokes an older proposal. Approvals are single-use and expire after two minutes. Pause cancels pending work but cannot undo an action already dispatched. Jarvis and Friday are presentation choices with identical permissions, not separate autonomous agents.

## AI that interprets requests

Local patterns are the fast offline path—not the only path. In the **native app**, select **AI settings** to configure a provider, then **Interpret with AI** for wording the local planner does not understand. The enabled-by-default checkbox beneath the input offers this automatically after a local miss once AI is configured; **every transmission still requires confirmation**.

AI can propose one shortcut launch, website/search, exact request-supplied HTTPS navigation or media-key action; or a **local-only follow-up intent** for app discovery, project selection or a ChatGPT research draft. It can answer or ask for clarification. It cannot supply a local app-selection handle, choose your project file, run model-generated code, invent a URL, or approve its own proposal. An allowed action can still misunderstand your intent: **read the exact action before allowing it**.

### Local model (Ollama)

Install Ollama and download a model separately, appropriate for your RAM/CPU. In **AI settings** choose:

- Preset: **Ollama (optional local model)**
- Base URL: `http://127.0.0.1:11434` (blank uses this default)
- Model: the exact name of your installed model
- API key: blank

Select **Apply for this session**. No model is bundled or automatically downloaded. Small models may return invalid JSON; that fails closed with a useful error, not execution. Local inference can use substantial resources even though the assistant itself has no bundled inference engine.

### Cloud / OpenAI-compatible API

Choose a named cloud preset, or **Custom OpenAI-compatible** and the provider's direct **HTTPS base URL** (usually ending in `/v1`), its exact model name, and an API key if required. The adapter appends `/chat/completions`. Cloud requests may incur costs and follow the provider's retention policy. Only the current request and fixed capability instructions are sent—not files, screen content, activity or conversation history. Keys are request headers, never prompt content.

Settings/credentials entered in the app stay in memory for the session; **they are not saved to disk**. An OS credential vault is not yet implemented. Do not paste secrets into requests or share them in issues/chat.

For repeat launches, provider configuration can also come from the launch environment:

```powershell
$env:COMPCONTROL_PROVIDER = 'ollama'
$env:COMPCONTROL_MODEL = 'your-installed-model'
py -3 -m compcontrol
```

Optional variables: `COMPCONTROL_BASE_URL`, `COMPCONTROL_API_KEY`. Use a trusted secret manager/launcher for keys, not source files or command history.

## Other modes

```powershell
py -3 -m compcontrol --demo          # native simulation; no desktop effects or AI
py -3 -m compcontrol --cli           # terminal, local skills only
py -3 -m compcontrol --web           # legacy optional local browser interface
py -3 -m compcontrol --web --demo    # browser simulation, not remote desktop control
py -3 -m unittest discover -s tests -v
```

Linux/macOS support simulations only. Native demo requires Tk and a display. For a headless preview use `python3 -m compcontrol --web --demo --host 0.0.0.0 --no-open`. The browser UI is retained for diagnostics/demo, **not the primary product**, and its AI mode is text-only; AI action interpretation is currently in the native app.

## Boundaries and release status

- No model-generated shell/code, direct project-file editing/deletion, automatic installs, managed downloads, arbitrary plugins, screenshots, microphone capture, account sign-in automation, purchases, scraping or telemetry. Patch export creates a new file outside the project. User-selected executables are powerful programs; only launch ones you trust.
- Installed-app discovery and user-selected executables complement shortcut paths. Explicit HTTPS URLs and bounded encoded search queries are supported; no AI-supplied executable path or PATH lookup. Preview shows observed target and native confirmation is still required.
- Native mode opens no listening port. Optional real web mode is loopback-only with bearer auth, Host/Origin validation, CSP and independent native consent. Never expose it through a tunnel.
- In-memory activity contains action labels/status only, not prompts or search queries. Destination sites, browser history, providers and the OS may retain data independently.
- Windows Start-menu package IDs and manually selected classic executables need real Windows verification; non-Start/portable apps need manual executable selection. “Dispatched” is not proof that an app loaded or media played.
- No always-listening voice, general desktop automation, Android companion, tray service or signed installer yet.
- Native interface/hotkey, real provider inference and packaged executable **still require Windows acceptance testing**. No measured memory/startup claims are made. Linux tests mock OS dispatch; see the checklist below.

## Build and development

Runtime: Python standard library + Tcl/Tk. No Node build, CDN, Electron, WebView or third-party runtime packages for the native UI.

`scripts/build-windows.ps1` creates an **unsigned, windowed, folder-based executable** with PyInstaller. Run it on Windows; distribute the entire `dist/CompControl` folder, not just the EXE. The build downloads a pinned build dependency. A manual GitHub Actions packaging workflow is included, but has not been run in this session. Do not disable Windows security to run untrusted binaries.

- [Broader Windows assistant direction and implemented boundaries](docs/capable-assistant.md)
- [Architecture](docs/architecture.md)
- [Threat model](docs/threat-model.md)
- [Research and design choices](docs/research.md)
- [Windows acceptance checklist](docs/windows-testing.md)
- [Roadmap and release gates](docs/roadmap.md)
- [Current implementation and validation notes](docs/implementation-notes.md)
