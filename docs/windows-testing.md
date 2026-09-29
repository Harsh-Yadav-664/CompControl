# Windows acceptance checklist

**Not yet executed on a real Windows desktop in this session.** Automated OS dispatch uses mocks; native UI integration tests skip where Tcl/Tk/display is absent. Do not confuse mock passes with Windows validation.

Use Windows 10/11, 64-bit Python 3.10+, Tcl/Tk enabled, a standard user account and normal browser/app installations. No elevation.

## Native app / widget

- [ ] `py -3 -m compcontrol` opens a native window, not a browser. Confirm no HTTP port 8765 starts listening.
- [ ] `scripts/start-windows.pyw` opens without a persistent console; `.cmd` supplies diagnostics if launch fails.
- [ ] Widget and Pin on top toggle correctly; input, action details and approval controls remain usable at 100%, 150%, 200% DPI and on smaller displays. Details scroll, never silently truncate.
- [ ] Minimize and summon with Ctrl+Alt+Space; test with another app owning that shortcut. Conflict notice appears and taskbar access still works.
- [ ] Ctrl+L focuses request; Enter in request plans only; Esc cancels; Ctrl+. pauses, including while the native confirmation dialog is open.
- [ ] Close exits without a hidden background app. Relaunch releases/reacquires the hotkey. Verify keyboard navigation and screen-reader behavior; accessibility is not yet certified.

## Effects and consent

- [ ] `open Calculator`: no execution until Review & approve, then Allow once. Cancel/close/Escape/Return in dialog cause no execution. Test expiry while dialog is open.
- [ ] Changing the request or browser invalidates an older approval immediately, even if the new request is malformed.
- [ ] `open a youtube tab and find Sidemen videos` → YouTube results. Also test `show me Sidemen videos on YouTube` and explicit Chrome/Brave selection.
- [ ] Spotify search and liked songs use the URI scheme with default handler; explicit browser choice retains HTTPS; verify the actual installed Spotify client. No automatic login, track selection or false playback claim.
- [ ] Launch Notepad/Paint/Explorer/Settings and installed Chrome/Brave/Edge/Spotify. Missing installations fail explicitly without an unintended fallback.
- [ ] Media keys affect the active player with toggle wording; no assumed current state.
- [ ] Activity shows only labels/status, not raw searches. Clear removes activity and pending work.

## Newly added Windows workflows (0.4.0; unverified here)

- [ ] With AI off, `open Visual Studio Code` proposes local discovery, never a guessed executable. Discover apps lists distinct results, selecting an exact packaged entry shows full AppID and asks for native consent; verify AppsFolder activation on Windows 10 and 11. A spoofed classic shortcut is not launched as a package.
- [ ] Classic or portable app: select its actual trusted `.exe`, review full path/hash/no arguments, approve once; altered or missing executable before confirmation is refused. Test in a disposable VM first; any executable can perform its own effects after launch. Check package discovery on common Store and desktop installations and non-ASCII app names.
- [ ] Explicit HTTPS URL is displayed exactly, then opens selected browser. Install/download wording only opens a Google search for an official source. A model-invented URL must fail. Never auto-run downloads. Verify errors from malformed URLs.
- [ ] Project files: choose root and exact UTF-8 file (including same-prefix filenames), verify unique replacement and preview. CRLF/no-final-newline, changed file, reparse point/symlink, hardlink, overwrite and in-project export must refuse or preserve originals. Exported patch goes through broker and native one-use approval. Open exported patch outside project; no source modification. Check behavior on OneDrive, network and FAT volumes (currently unsupported/reject where identity cannot be guaranteed).
- [ ] Close/cancel/pause/edit replacement or input while export dialog is open: no stale export should occur. Reopen and review again. No file content reaches AI provider.
- [ ] ChatGPT handoff shows draft and opens chatgpt.com only; new chat/Deep research selection and submission remain manual. Check account eligibility and actual UI independently.

## AI

- [ ] Configure Groq/Gemini/NVIDIA cloud API (or optional Ollama) in AI settings. Ask `open spify and play maati song`: inspect the interpretation; do not assume a small model is correct.
- [ ] Every transmission shows provider/model/current request disclosure. Declining sends nothing. Optional fallback offers interpretation only after a local miss.
- [ ] Valid AI action shows an AI proposal label, locally generated exact action/destination and requires native approval. Message-only output never enables approval.
- [ ] Invalid JSON, extra fields, unsupported action, provider error/timeout produce a readable error and no effect. There is no automatic retry.
- [ ] Edit, Cancel, Pause/Resume, Clear or submit another request while inference is in progress. Late result must not replace current work or restore approval.
- [ ] Pause and local planning remain responsive during network I/O. Cloud and local provider settings cannot silently switch while a request is in flight.
- [ ] Cloud endpoint uses HTTPS; key is masked and absent from UI errors, prompts and activity. Session settings are gone after restart; no provider configuration is saved to disk by the app.
- [ ] Native demo ignores provider environment settings and never performs effects or network inference.

## Release gates

- [ ] `py -3 -m unittest discover -s tests -v`: GUI tests actually run, not skip. `py -3 -m compileall -q compcontrol scripts` passes.
- [ ] Build with `scripts/build-windows.ps1`; launch the entire output folder on a clean VM without Python. Verify UI, Tcl/Tk, native confirmation and hotkey work without a console. Packaged startup errors show a readable dialog.
- [ ] Measure cold startup, idle memory/CPU, and response latency with AI off; report inference resource use separately. Do not invent performance numbers.
- [ ] Optional `--web` remains loopback-only in real mode. External binds only work with `--demo`; demo disables providers/effects.
- [ ] Review signing/distribution and user support before publishing a release. Do not ask users to disable Windows security.
