# Windows setup — native app, cloud AI, no Ollama

## 1. Use the current files, not the old browser preview

Extract **CompControl-Windows-Source-0.4.0.zip** to a new folder, for example:

```text
C:\Users\YourName\Downloads\CompControl-Windows-Source-0.4.0\
```

Use **Extract All**. Do not run files inside the ZIP. Keep the `compcontrol` and `scripts` folders alongside the launchers. This source ZIP includes the native UI and fixes even if your existing checkout/browser preview is older. It is **not an EXE installer**; it needs Python once.

You should see these top-level files:

- `Start CompControl.cmd`
- `Start Widget.cmd`
- `Check Windows Setup.cmd`
- `START HERE.txt`

If those files are absent, this is not the supplied 0.4.0 package. Do not overwrite your old checkout blindly; use a new extracted folder.

## 2. Install Python once

Install **Python 3.12, Windows installer (64-bit)** from https://www.python.org/downloads/windows/ . During installation enable:

- **tcl/tk and IDLE** (the desktop window toolkit)
- **Python launcher** (`py`)
- **Add python.exe to PATH** (helpful fallback)

Use your regular account. No administrator launch, `pip install`, Node, Ollama, GPU, Docker or local model download is required by this app. For cloud AI, the remote provider runs the model.

## 3. Double-click to run

Double-click **Start CompControl.cmd**. It checks Python/Tk and the exact YouTube parser regression, starts the native window with `pythonw.exe`, then closes the temporary console.

Or double-click **Start Widget.cmd** to start compact and pinned on top. The title includes **CompControl 0.4.0 · Native desktop**. The assistant window has slate/violet styling, no browser address bar and no web server.

- **Ctrl+Alt+Space:** summon the already-running window on Windows.
- **Ctrl+L:** focus request; **Enter:** prepare a plan, not approve.
- **Esc:** cancel pending work. **Ctrl+.** inside the app/approval dialog: pause actions.
- Close the window to exit. No hidden tray or startup service remains.

A hotkey conflict is shown in the footer; use the taskbar if another program owns it.

### Terminal alternative

In PowerShell, from the extracted folder:

```powershell
py -3 -m compcontrol
# Or:
py -3 -m compcontrol --widget
```

**Do not add `--web` or `--demo`** when testing real Windows actions. `--web` explicitly selects the old browser UI; `--demo` deliberately simulates effects and disables AI.

## 4. Test YouTube before configuring AI

Type exactly:

```text
open yt and search for mr whose the boss
```

Select **Plan request → Review & approve… → Allow once**. The destination should be:

```text
https://www.youtube.com/results?search_query=mr+whose+the+boss
```

This uses a local skill: **no AI request or API key is required**. It opens search results in your browser after approval. “Without browser” refers to the assistant UI: visiting YouTube itself naturally opens a browser. Nothing starts playback automatically. Also test `open calculator` to verify an actual Windows app launch.

## 5. Discover apps, preview file changes, or hand off research

- Try `open Visual Studio Code`: choose **Discover apps → Scan Start menu** and inspect the exact entry. Packaged apps can be selected; for classic/portable apps select the actual `.exe` yourself (no shortcut arguments are run). The app is not signature-scanned. Approve only a trusted executable.
- Try `project files`: click **Project files**, choose a project root and exact UTF-8 file, type an exact unique replacement, inspect the diff, and export a **new** patch outside the project. The original is never changed. Do not expect an autonomous code editor or delete tool yet.
- Try `ask ChatGPT to do deep research on battery recycling`: review the displayed draft, approve navigation, and start the new Deep research chat yourself if available to your account. No browser prompt is submitted by CompControl.
- Explicit `open https://...` navigation can help reach a download page. CompControl does not download/manage/install files itself yet.

See [capability plan and boundaries](capable-assistant.md). The source archive must be rebuilt for this version; an older 0.3.1 ZIP does not contain these features.

## 6. Add cloud AI (choose one provider)

Open **AI settings**. Choose a named preset; URL and starting model are filled for you. Paste the key **inside the app**, not into chat, source files or the request box.

| Preset | Key/account portal | Starting text model | API base URL |
|---|---|---|---|
| Groq (cloud) | https://console.groq.com/keys | `openai/gpt-oss-20b` | `https://api.groq.com/openai/v1` |
| Gemini (cloud) | https://aistudio.google.com/apikey | `gemini-2.5-flash-lite` | `https://generativelanguage.googleapis.com/v1beta/openai` |
| NVIDIA NIM (cloud) | https://build.nvidia.com/ — choose a model and Get API Key | `meta/llama-3.3-70b-instruct` | `https://integrate.api.nvidia.com/v1` |

Then:

1. Select **Test AI setup** and accept the fixed test-request disclosure.
2. A successful test confirms the model returned the expected Calculator proposal. It **does not launch Calculator** and does not send your current request/history.
3. Select **Apply for this session**.
4. Type normally and select **Plan request**. Recognized local skills work immediately as proposals. For unfamiliar wording, AI interpretation is offered by default with a transmission disclosure; **Interpret with AI** can also be used directly.
5. Review any returned action before allowing it. A model can misunderstand intent even with valid JSON.

Models and access change. The prefilled IDs are starting points, not access guarantees. If you receive a 404/access error, copy a currently enabled **text chat model ID** from that provider's console. Avoid image/audio-only models. Keys and settings are currently **session-only**: you must enter them again after restarting; the app does not write credentials to disk.

**Free usage is not unlimited or guaranteed.** Confirm the free plan/development quota and data terms in your own provider account. A provider may require account eligibility, impose region/model restrictions, or charge if billing is enabled. CompControl cannot inspect or cap your provider bill and does not silently switch providers, upgrade plans, retry, or bypass limits. On HTTP 429 it stops and explains the quota/rate-limit problem. Do not send sensitive text until you have checked the provider's retention terms.

### Official adapter references (reviewed 2026-09-28)

- Groq OpenAI-compatible base URL: [1](https://console.groq.com/docs/openai). Model IDs and access: https://console.groq.com/docs/models ; account limits: https://console.groq.com/settings/limits .
- Gemini OpenAI-compatible API, Bearer authentication and model/thinking options: [1](https://ai.google.dev/gemini-api/docs/openai). Pricing and free-tier data terms: https://ai.google.dev/gemini-api/docs/pricing .
- NVIDIA hosted chat-completion endpoint and compatibility: [1](https://docs.api.nvidia.com/nim/reference/create_chat_completion_v1_chat_completions_post). Model list: [2](https://docs.api.nvidia.com/nim/reference/llm-apis). Hosted development access: https://build.nvidia.com/explore/discover . This is the hosted API, **not** a local NIM container.

## Troubleshooting

| Symptom | What to do |
|---|---|
| Green browser page / “outside my safe toolkit” | Close the old preview. Extract this ZIP and use its top-level launcher. The native title includes 0.4.0. |
| Window does not appear | Double-click `Check Windows Setup.cmd`. It leaves diagnostics visible; no API call or desktop effect. |
| `py` not recognized / Store prompt | Install standard Python with the launcher; reopen PowerShell. Launchers also try `python` if `py` is missing. |
| Tk missing | Modify/reinstall Python with **tcl/tk and IDLE**. `py -3 -m tkinter` should open a small test window. |
| CompControl module missing | Extract the entire ZIP first. Run from the folder containing `compcontrol`, not from inside `scripts`. |
| API 401 | Replace the key for the selected provider. Switching provider/endpoint clears the old key to avoid sending it to the wrong service. |
| API 403/404 | Check account access, exact text model ID and the preset endpoint. |
| API 429 | Free quota/rate limit exhausted. Wait for its reset or choose another provider yourself. No paid fallback happens. |
| Wrong/malformed model proposal | No execution is accepted. Rephrase, choose another text model, or use a local skill. |
| Browser missing | Select `default` or install your selected Chrome/Brave/Edge normally. No silent substitution. |

## If you want a Python-free EXE later

Build **on Windows** from this folder:

```powershell
powershell -NoProfile -File .\scripts\build-windows.ps1
```

This installs a pinned **build-only** PyInstaller dependency and creates `dist\CompControl\CompControl.exe`. Keep/distribute the **entire** `dist\CompControl` folder. The build is unsigned. Do not disable Windows security or run elevated to bypass a block. If your PowerShell policy blocks local scripts, follow your device's policy rather than bypassing it.

The attached deliverable is source, not a signed/Windows-tested installer. Automated tests exercise the Windows dispatcher with mocks; this Linux sandbox cannot certify actual Windows rendering, global hotkeys or packaged EXE behavior. The app includes real Windows dispatch paths—“not Windows-tested here” does not mean “browser demo only.”
