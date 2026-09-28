# Research and product choices

Reviewed 2026-09-28. Sources inform design; no external project code is copied into this prototype.

- Open Interpreter's community-maintained Python fork describes local code execution and confirmation before execution. CompControl intentionally does **not** adopt general code execution; a small registered capability boundary is easier to reason about. [1](https://github.com/endolith/open-interpreter)
- Home Assistant documents a composable voice pipeline (speech-to-text, conversation/intent processing, text-to-speech), including local Whisper and Piper. This supports separating future audio from the command broker rather than embedding microphone capture in every feature. Audio is deferred here. [3](https://www.home-assistant.io/blog/2023/04/27/year-of-the-voice-chapter-2/)
- Spotify's Start/Resume Playback API requires Premium. We expose ordinary search/liked-page navigation and do not claim free API playback or try to evade restrictions. Future playback integration must use supported OAuth/API flows and eligible accounts. [1](https://developer.spotify.com/documentation/web-api/reference/start-a-users-playback)

Decision: deterministic-first, explicit consent, no LLM-to-OS path, no always-on audio, no unrestricted plugin/runtime execution. Keep local skills free to run; disclose hardware costs of local inference and charges/privacy of paid endpoints. Do not present this prototype as a full replacement for any researched project.
