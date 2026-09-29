# Research and product choices

Reviewed 2026-09-28. These sources inform design; no external project source code is copied into CompControl. Features described here are design inspiration, not claims that every upstream feature is implemented or necessary.

## Desktop-first ergonomics

- **Flow Launcher** describes a customizable summon hotkey (Alt+Space by default), app launching, web search, calculator and themes. Adopt the compact request-first surface, quickly reachable window, familiar local utilities and low visual noise. CompControl uses Ctrl+Alt+Space to avoid taking Flow's default, reports conflicts and retains taskbar access. Do **not** copy its shell/admin command or unrestricted plugin surface into an AI assistant. [Flow Launcher](https://www.flowlauncher.com/)
- **PowerToys Command Palette** documents keyboard-first navigation, an optional compact search box, user-pinned commands and a dock. Adopt compact mode, visible shortcuts, Enter-to-plan, Escape-to-cancel and an optional always-on-top window. This MVP's Widget is a smaller ordinary window, **not** a Windows Widgets-board extension or PowerToys-style dock. File indexing, clipboard history, system maintenance and extensions are not automatically in scope. [Microsoft overview](https://learn.microsoft.com/en-us/windows/powertoys/command-palette/overview)

## AI assistance and control

- **Open Interpreter** exposes an execution-policy layer beneath approvals. The relevant idea is a policy boundary independent of the model and UI—not a claim that model instructions alone provide safety. CompControl deliberately omits code execution: the AI proposes one typed capability, a strict parser and broker validate it, and the user confirms the exact destination. [3](https://www.openinterpreter.com/docs/terminal/execpolicy)
- The upstream Open Interpreter README now describes a coding-agent architecture and computer-use integrations. Its broader automation surface is not a lightweight drop-in dependency for this personal widget. CompControl should not pretend it has that scope merely because it has an LLM adapter. [Upstream README](https://raw.githubusercontent.com/OpenInterpreter/open-interpreter/main/README.md)

## Previously recorded research / future integrations

- **Home Assistant** separates speech-to-text, conversation/intent and text-to-speech, with local voice options. Retain a separate future voice pipeline rather than embedding always-on capture into command execution. Voice is not implemented here. [Voice architecture](https://www.home-assistant.io/blog/2023/04/27/year-of-the-voice-chapter-2/)
- **Spotify's Start/Resume Playback API** requires an eligible Premium user. Current functionality is search/liked-page navigation plus Windows media keys, not API playback. Do not promise free autonomous playback or bypass provider restrictions; future integration requires supported OAuth and eligibility checks. [Playback API](https://developer.spotify.com/documentation/web-api/reference/start-a-users-playback)

## Decisions implemented in this iteration

1. Native Tk is the default: no browser page or HTTP server at launch, no new third-party runtime dependency. Replace green-heavy presentation with slate surfaces and restrained violet controls.
2. Local parsing handles normal site-opening/search composites, including the user's YouTube example. AI is an explicit fallback, not limited to unrelated chat.
3. Provider setup exists in the native UI and is session-only; every request discloses its destination and requires permission. Local models remain separate resource-heavy processes.
4. Untrusted structured proposals never become scripts, arbitrary URLs, extra actions or their own approval descriptions. AI output is useful interpretation, not execution authority.
5. Widget mode, pinning, Windows summon hotkey, shortcuts, activity and cancellation make a small desktop workflow possible. Test on real Windows before calling this ready for distribution.

## Expanded direction (0.4.0)

The earlier fixed-capability policy is no longer the product ceiling. See [capable-assistant.md](capable-assistant.md) for observed-target architecture, Start-menu discovery, project-patch boundary, WinGet research and ChatGPT handoff. Execution is still one effect per approval; multiple planners do not inherit OS authority.
