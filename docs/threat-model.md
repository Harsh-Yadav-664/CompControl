# Threat model · v0.2

Assets: local files/device integrity, accounts, provider credentials, search/privacy context. Trusted: OS, Python distribution, this checkout, app binaries in normal install roots, explicitly selected provider. Do not run as administrator.

| Threat | Implemented boundary / residual risk |
|---|---|
| Model/prompt injection | AI text is displayed as text, never parsed into an executable plan. No model tool access. A user may still manually follow bad advice. |
| Shell or argument injection | Fixed app paths; no PATH lookup, shell strings, user executables, eval or file mutation. Search queries are encoded into fixed HTTPS URLs. Local malware replacing trusted app installations is out of scope. |
| Unauthorized web request / DNS rebinding | Random bearer token, exact loopback Host, same Origin, JSON-only mutation, no CORS, no query-token auth. Native consent is independent of browser approval. |
| Clickjacking/XSS | Local frame denial, strict self-only CSP, textContent for user/provider text. Public iframe-enabled demo has no executor/provider. Browser extensions or a compromised browser can read page memory. |
| Approval replay/race | Immutable server-side pending action; one-use ID, two-minute expiry, single execution lock; pause/clear revokes waiting work. Already committed OS dispatch cannot be recalled. |
| Accidental native approval | Cancel owns focus; Return/Escape deny; Allow requires deliberate click after review delay. Native dialog closes when revoked/expired. OS malware can still synthesize input. |
| Secret exfiltration | Keys not in browser/API state/logs/prompts; HTTPS for cloud providers; redirects/proxies disabled. Environment/process memory is not an OS vault and is readable to sufficiently privileged local processes. |
| Sensitive logging | No access logs, saved transcripts or query-bearing audit entries. Browser history, destination sites, provider and OS may retain data independently. |
| Remote compromise | No real non-loopback bind; demo disables actual executor and providers. Reverse-proxying local mode is unsupported. No Android remote listener. |
| Denial of service | Request/response bounds, pending-plan bound, limited event ring, request/provider timeouts, single model call. Standard-library threaded server is not hardened against sustained public DoS; demo must not contain private data. |
| Service restrictions | Search/deep-link navigation and OS media keys only. No login automation, CAPTCHA evasion, spam, scraping or Premium bypass. No guarantee of third-party account outcomes. |

## Security tests and known gaps

Unit tests cover planner allowlists, hostile inputs, bounded arithmetic, replay, races, revocation, HTTP Host/Origin/auth, forged client actions, provider redirects and secret redaction. Windows actions are mocked in this Linux environment. See the manual Windows acceptance checklist before relying on the prototype.

Not implemented: signed releases, independent audit, encrypted memory, OS credential store, plugin sandbox, remote pairing, OAuth. A local administrator or malware with your user's privileges remains capable of interfering with Python, environment variables, binaries and browser state. Confirmation reduces accidental execution, not all compromise.

Report security concerns privately to the repository owner; do not post live credentials in issues. Keep private launch URLs and provider keys private. If credentials have been shared outside their intended secret channel, revoke them and review activity.
