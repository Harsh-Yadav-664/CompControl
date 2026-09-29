# Implementation notes · 2026-09-28

## User direction addressed in source 0.4.0

The native Tk app/widget is primary; the green browser demo is optional and not the way to launch. Everyday YouTube/Spotify searches are local and do not require a model. Hosted Groq/Gemini/NVIDIA AI can propose typed actions; approval remains separate from interpretation.

The earlier small app dictionary is no longer the eventual product limit. A local Windows Start-menu scan can find packaged apps; for classic entries, the user selects an actual executable with a path/hash preview and no hidden shortcut arguments. `install X` and `download X` find Google results for the official Windows download page only. Explicit HTTPS URLs can be reviewed. Spotify uses its `spotify:` URI handoff for the default handler, with HTTPS if the user selects a browser.

Project-file support currently stops at user-selected exact UTF-8 text files, unique exact replacement previews, and a new patch export outside the project. Export returns through the central broker and native one-use approval. The original is not directly edited, deleted or automatically patched. ChatGPT research is a manual new-chat/deep-research handoff, not automatic form submission. See [capable-assistant.md](capable-assistant.md).

## Authority and target controls

- AI outputs one strict structured action or local follow-up intent; it cannot create local handles or provide model code/args. Model-suggested navigation URLs must exactly occur in the disclosed request.
- Start-menu names/AppIDs come from a constant read-only PowerShell script, locally and on explicit scan; package IDs are checked against installed package manifests. Exact selection precedes broker approval.
- Selected EXEs are bounded, hashed asynchronously and rechecked; hash is identity evidence, **not** signature/publisher/malware verification. A trusted user's choice can still be dangerous.
- Selected project/file identity/hash and exact diff are rechecked at export. A new patch is created with no overwrite; no project write or patch application.
- Every external effect is one-use, two-minute and separately approved in the native dialog. No auto retry, permission blanket or agent consensus shortcut.
- No generated shell/code execution or automatic install. PowerShell is a constant local inventory query only.

## Validation and caveats

Latest local Linux validation:

- `python -m unittest discover -s tests -q`: **100 discovered; 93 passed; 7 skipped** because Tcl/Tk/display are missing.
- `python -m compileall -q compcontrol scripts tests`: passed.
- `git diff --check`: passed for tracked content; run explicit trailing-space checks over untracked source before packaging.
- Mocked Windows tests cover app inventory, selected executable dispatch/revalidation, screenshot query dispatch, Spotify deep-link destination and patch approval. Workspace tests apply the generated patch only to a disposable copy; CompControl itself never applies it.

Not validated on Windows: Tk layout/hotkeys/DPI, `Get-StartApps`/AppX parsing, AppsFolder app activation, Spotify URI handler, real consent/dispatch, Windows reparse/identity guarantees, cloud provider requests or EXE packaging. No provider request, package install, project mutation or software download occurred. Seven GUI tests skip here. See [windows-testing.md](windows-testing.md).

No signed/released EXE, automatic installer, direct edit/delete, general UI automation, browser login control, autonomous multi-step runner, voice, Android support or performance measurements are claimed.
