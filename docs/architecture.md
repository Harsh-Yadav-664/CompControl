# Architecture and technology choices

## Prototype boundaries

`compcontrol.core.Assistant` maps a complete normalized phrase to a fixed intent. It does not invoke a model, parse executable code, access the network, or retain history. An `Intent` is a named, documented handler; tools return a `Result` for the UI to display. The CLI in `compcontrol.__main__` is replaceable and owns no action policy.

## Proposed product architecture (not implemented)

- **Windows-first shell:** evaluate a native .NET / WinUI 3 frontend for Windows integration and low idle overhead. Keep policy/core behind a narrow interface. Do not introduce an embedded browser UI or heavyweight runtime without demonstrating a usability need.
- **Core/action broker:** typed intent and capability interfaces, default-deny registry, timeouts, cancellation, and a per-action confirmation policy. Launch only fixed, documented app actions; never build shell strings from prompts.
- **AI adapter:** optional provider abstraction. Deterministic skills handle simple requests; an LLM may classify/plan but can only propose registered actions. Start with local inference compatibility (Ollama or OpenAI-compatible endpoint); later providers are user-selected plugins. Validate every model response as untrusted structured data.
- **Integrations:** separate narrow adapters (browser search, media playback) using supported URLs/APIs and user-visible app control. Do not automate logins, evade service restrictions, scrape at scale, or attempt platform policy circumvention. Resolve ambiguity and show the target before playback or external side effects.
- **Storage/secrets:** minimal local settings; Windows Credential Manager/DPAPI for secrets if introduced. Never log authorization headers, secrets, raw voice recordings, or full private prompts by default.
- **Voice:** optional local speech-to-text and text-to-speech, loaded on demand; push-to-talk and visible microphone state. No always-on capture by default.
- **Android (later):** companion client, not a public internet-exposed desktop agent. Pair explicitly using short-lived one-time code and device approval; authenticated TLS, scoped permissions, revocation, and no port listening until enabled.

## Stack decision

This initial core uses Python standard library to keep the proof of behavior easy to run and audit. For the eventual Windows product, benchmark a native .NET UI/core against a Python packaged app before committing. Free-to-run means no mandatory hosted API: local deterministic actions work offline; local models are optional and hardware-dependent. Paid APIs should be opt-in with clear disclosure and provider-specific budget controls. Android is a later client milestone, not a present compatibility claim.
