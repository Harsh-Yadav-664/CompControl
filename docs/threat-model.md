# Threat model (initial)

## Protected assets

User files, account credentials, microphone/audio, browsing context, and the integrity of the Windows device. The prototype currently accesses none of these except launching Calculator on an explicit exact command.

## Threats and controls

| Threat | Current/proposed control |
|---|---|
| Prompt injection or ambiguous wording causes an unintended action | Current exact-match allowlist; future model output can only select registered capabilities and never change policy. |
| Arbitrary command execution / destructive filesystem access | No shell or file tools; future actions must be narrowly implemented, least-privilege, confirmed, and tested. |
| Secret leakage to model, logs, or repo | No credentials or provider calls in prototype. Future secrets in OS credential storage; redact logs; keep `.env` and keys out of Git. |
| Malicious webpage content induces actions | No web access currently. Future webpage text is untrusted data, not instructions; external effects require preview and confirmation. |
| Remote attacker controls desktop | No network listener or remote control in prototype. Future remote mode disabled by default, paired devices, TLS, scoped auth, revocation, rate limits, replay defense. |
| Supply-chain or plugin compromise | No plugins currently. Future integrations reviewed, pinned, least-privilege, and isolated where practical. |
| Service account/platform bans or restrictions | Use documented user-facing interactions and supported APIs; no credential automation, scraping, spam, evasion, or policy circumvention. |

## Known limits

A confirmation dialog does not make an unsafe capability safe, and model output cannot reliably neutralize hostile content. Do not claim perfect security. Before remote access, browser control, file operations, or third-party credentials are added, document abuse cases and conduct focused security review. Report vulnerabilities privately to the maintainers; do not include live secrets in issues.
