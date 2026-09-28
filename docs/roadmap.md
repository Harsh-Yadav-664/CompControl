# Roadmap

## v0.2 source prototype (implemented)
- Shared Jarvis/Friday command center, skill library, shortcuts, preferences and in-memory activity.
- Registered Windows apps, fixed-site search, liked songs page, media-key actions, local arithmetic/time.
- Typed plan → expiring one-use broker → independent native consent → Windows dispatch.
- Explicit local/cloud text AI adapters without tool execution; demo disables both provider and desktop executor.
- CLI, tests, source launch/build scripts, architecture and threat documentation.

## Next gates (not implemented)
1. Real Windows acceptance + measured memory/latency + packaged executable smoke tests.
2. OS credential-store integration and signed release/distribution strategy.
3. Optional push-to-talk local speech with visible capture, model download consent and hardware benchmarks.
4. User-authorized OAuth media integration subject to provider restrictions; no free playback promises.
5. Additional typed, tested skills. File modifications require separate permission, scope, preview, rollback and audit design.
6. Android companion only after pairing, TLS, revocable device credentials and remote-action threat review.

GitHub issues #3–#5 track the MVP implementation. PR #2 carries the session branch. Items should close after verification/merge, not for artificial timing targets. API permissions may prevent issue edits or merges; do not substitute credentials shared in chat.
