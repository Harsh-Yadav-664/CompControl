# Roadmap · Windows-first assistant

## 0.4.0 source increment (implemented locally; not Windows-verified)
- Native desktop + widget and session-only hosted AI.
- YouTube local search; Spotify desktop URI handoff; explicit HTTPS destinations.
- Discover Start-menu apps locally; selected packaged app ID or actual `.exe` needs separate native approval. No hidden shortcut arguments.
- Local project/file selection, exact replacement preview and broker-approved patch export outside project. No source write, apply or delete.
- AI can request a local discovery/file/research follow-up. ChatGPT research is a manual draft/new-chat handoff.
- `install X`/`download X` finds Google results for the official Windows download page; it does not download or install.

## Next release gates
1. **Real Windows validation:** run Tk tests, verify Start-menu/AppX results on Windows 10/11, custom executables, Spotify URI handoff, file identity/reparse behavior, cancellation, DPI, accessibility and packaged EXE.
2. **Useful code assistance:** optionally send one user-selected file to AI only after a prominent path/provider/content disclosure; parse a strict exact patch; render full local diff; never enable writes until transaction/rollback is reviewed. Handle prompt injection in file content as untrusted data.
3. **Download/install:** add WinGet discovery first. Show exact ID, source, publisher, version, architecture, license and elevation requirements; re-resolve before launch; preserve native UAC; verify installed version. Separate download from execution. Never run a model-invented package ID/script.
4. **Safe direct edits:** handle-based Windows target validation through commit, same-volume staging/atomic replacement, recoverable private backup, root/file identity checks, race testing, diff-bound approval and result verification.
5. **Browser/computer use:** selected window/tab, observed UI snapshots and actions, re-observe on state changes, untrusted page content, confirmations for external submissions/downloads; do not reuse browser auth silently.
6. **Task orchestration/multi-agent:** planner may prepare an explicit DAG and specialists may review, but every effect is authorized by deterministic target verification and an expiring per-effect broker grant. Stop on unexpected state or partial failure. Agent consensus is not permission.
7. **Voice, credential vault, signed distribution and Android companion:** independent privacy/elevation/pairing threat models before implementation.

This session cannot perform remote GitHub operations. Work remains local on its Arena branch; do not claim a release, PR, push or Windows CI run.
