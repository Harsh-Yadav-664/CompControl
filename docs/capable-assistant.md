# From command launcher to Windows assistant

Design and implementation status: 2026-09-28, source increment 0.4.0.

## Product direction

A short app/action allowlist must not define the product's eventual capabilities. The safety boundary is **what target has actually been observed, what change has been reviewed, and what authority has been granted**, not whether the app's name appeared in a Python dictionary.

That does not mean letting an LLM emit a PowerShell script and treating an OK button as protection. A model may select the wrong project, misunderstand a download page, or read hostile instructions in a README. More models voting on the same bad target does not fix that.

## Architecture to grow into

1. **Coordinator:** interpret the goal, propose a task graph, expose assumptions and missing capabilities. It has no OS authority.
2. **Discovery adapters:** observe installed apps, package search results, selected workspace files, browser tabs and accessibility elements. Return provenance and session handles, not permissions. External content is data, not instructions.
3. **Specialist planners (optional):** file, software and browser planners can work from explicitly disclosed observations. Introduce separate model calls only when they improve results; hosted API latency/cost and privacy are real constraints.
4. **Deterministic target verifier:** resolve ambiguity, verify selected identities and preconditions, calculate the exact diff/download destination/installer invocation. A second model can critique intent, but cannot replace these checks.
5. **Approval broker:** bind an expiring one-use approval to the exact target, arguments, preconditions and changes. Approve the next effect, not a blanket task. Changing a target or receiving a new observation requires review again.
6. **Executor and result verifier:** execute only the reviewed effect, report evidence and stop on failure or drift. Distinguish dispatched, completed, verified, failed and cancelled. Never blindly retry a mutation.

Only parts of this architecture exist today. There is no task graph executor, autonomous multi-agent loop or general UI automation yet. `Broker` still permits one effect per approval. That is an execution granularity decision, not the planned capability ceiling.

## Implemented in 0.4.0

### Apps beyond the shortcut dictionary

- Native **Discover apps → Scan Start menu** reads names/AppIDs locally using a constant Windows PowerShell script. No user/model text enters the script; no profile, PATH lookup or execution-policy bypass.
- Package manifest IDs are cross-checked before treating an entry as a packaged application. A shortcut whose ID merely looks like a package is not sufficient.
- Filtering never auto-selects a result. Duplicate names remain separate rows with AppIDs.
- Packaged app launch uses a locally observed, expiring handle and Windows Explorer's AppsFolder activation. Its registration is rechecked after native consent. No custom arguments.
- Classic Start-menu entries can contain hidden shortcut arguments. This increment **does not launch those shortcuts**. Select the actual trusted `.exe` instead, also available for portable apps. The preview includes its absolute path, size-derived identity and SHA-256; dispatch rechecks it and passes no arguments. Working directory is the executable's directory, not the project.
- An executable header/hash is **not** a signature, malware or publisher verification. Any app you launch can act with your Windows user's permissions. Windows registration/executable replacement by a hostile concurrent process is outside the current guarantee; there remains a check-to-launch race. Do not run untrusted programs.
- Built-in names in `APP_NAMES` remain convenient local shortcuts, not the only applications that can be launched.

### Spotify desktop handoff

Spotify searches use `spotify:search:` and liked songs use `spotify:collection:tracks` when the default handler is selected, so Windows can hand them to the Spotify desktop app. Selecting Chrome/Edge/Brave explicitly keeps the HTTPS destination. Spotify deep-link support is account/app-version dependent and has not been checked on Windows here. It does not auto-select or play a track. [Spotify URI scheme](https://www.iana.org/assignments/uri-schemes/prov/spotify) · [Spotify desktop URI guidance](https://developer.spotify.com/documentation/web-api/concepts/spotify-uris-ids).

### General HTTPS navigation

`open https://example.org/` is no longer limited to named websites. Credentials, hidden characters and non-HTTPS schemes are rejected. AI navigation must exactly match a URL in the disclosed request; an invented installer URL is rejected by the provider boundary. The user still reviews it. Navigation can trigger a browser download; it does not manage the filename, verify the publisher or execute the downloaded file.

### Install/download request (search-only)

`install Blender` prepares a Google search for `Blender official download Windows`. The native preview says exactly that it opens search results only. It does not choose a publisher result, download files, run WinGet, bypass UAC or install software. WinGet execution waits for an exact, source-grounded package ID and version preview in a later increment.

### Project files: safe intermediate output, not direct mutation

**Project files → Select project → Select exact file → Preview patch → Export new patch** is a local-only manual workflow, not an AI coding agent.

- Exact project-relative path and on-disk spelling; no fuzzy filename selection or first search result.
- Reject traversal, ambiguous Windows names, alternate data stream syntax, hardlinks, symlinks and reparse points. Some legitimate files/locations are deliberately unsupported until Windows-specific handling exists.
- UTF-8, up to 256 KiB, exact-text replacement matching exactly once. CRLF and no-final-newline are preserved; mixed line endings are rejected.
- Source snapshot carries root/file identities, metadata and SHA-256. Recheck before preview and again before export. Changing the file consumes neither a guessed edit nor an automatic retry.
- Native diff, full target and base hash. Control/direction characters are escaped for display. Exports currently require an ASCII filename; UTF-8 content is supported. Patch export now has a local single-use handle and goes back through the central broker plus the native approval dialog; model/browser clients cannot create those handles.
- Create a **new `.patch` outside the project**, never overwrite an existing export. Originals and similarly named files remain unchanged. Changing replacement text invalidates the preview; export consent expires and can be cancelled/paused.
- Source/patch content stays local and is not passed to cloud AI. Export files intentionally contain source snippets/path/hash: store them privately.
- Generic patch tools do not enforce the root/hash written in the patch preamble. If you manually apply it, independently verify the project, base hash and diff. CompControl does not apply it or delete anything.

These checks address ordinary stale/wrong-target mistakes. They are not a hostile-filesystem sandbox; a malicious process can race path checks. Direct writes need a tested Windows handle-based transaction/backup design before being enabled.

### ChatGPT research handoff

`ask ChatGPT to do deep research on battery recycling` prepares a draft and an approved navigation to ChatGPT. **You** select New chat, choose Deep research if eligible, paste the draft and approve its research plan. CompControl does not select a browser tab, submit the prompt, spend research quota or claim completion. It does not read your login/session cookies.

## Next increments, not implemented promises

| Capability | Required target evidence and control |
|---|---|
| Install software | Search results with exact package ID, source, publisher, version and installer metadata; select one, inspect, approve one install, retain UAC/terms decisions; verify actual installed version. Never execute a model-invented ID. |
| Managed download | Exact URL and redirect chain, new destination, overwrite prevention, bounded stream, expected hash/signature where available; no auto-execution. |
| Direct file edit | Windows directory/file handles and identity checks through commit, exact diff, tested same-volume staging/atomic replace, recoverable backup with private ACL, stale-target refusal, verified result. |
| Delete/move | Exact selected entries and impact preview, protected boundaries, recoverable trash/move journal; no recursive wildcard deletion from model text. |
| Browser/UI tasks | Bind to selected window/tab and observed elements; reobserve before each action; treat page instructions as untrusted. Confirm external submissions independently. |
| Multi-step tasks | Observable step states, cancellation checkpoints, per-effect approvals and explicit partial-failure reporting. Do not simply remove the current broker limit. |

## References and decisions

- Microsoft's documented Start-menu discovery uses `Get-StartApps`; apps absent from Start are absent from that inventory. Package manifests provide package application IDs. This is why manual executable selection remains necessary. [1](https://learn.microsoft.com/en-us/windows/configuration/store/find-aumid)
- WinGet documents ID + exact match + explicit source to disambiguate installations. Future install execution must be grounded in observed package metadata rather than guessing a name. [1](https://learn.microsoft.com/en-us/windows/package-manager/winget/install)
- ChatGPT documents Deep research through `/Deepresearch`, the tools menu or sidebar. The present handoff keeps that selection and quota-consuming submission manual rather than pretending a URL selects the mode. [1](https://help.openai.com/en/articles/10500283-deep-research-in-chatgpt)
- See [earlier project research](research.md) for Flow Launcher, PowerToys and Open Interpreter design influences. Their earlier narrow scope is historical, superseded by the direction here.

## Verification caveat

Automated tests exercise target changes, wrong paths, duplicate text, links, patch formatting, cancellation/approval boundaries and mocked Windows dispatch. This Linux environment cannot verify actual Windows app activation, native Tk rendering, package inventory, cloud inference or executable packaging. Run the [Windows checklist](windows-testing.md) before treating this as a verified desktop release.
