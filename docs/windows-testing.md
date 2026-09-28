# Windows acceptance checklist

**Not yet executed on a real Windows desktop in this session.** Linux tests mock Windows calls; passing mocks is not proof of app integration.

Use Windows 10/11, 64-bit Python 3.10+, Tcl/Tk enabled, standard user account. Do not run elevated.

- [ ] Start `py -3 -m compcontrol`; UI opens via private URL; reload locks it; reopening printed URL works.
- [ ] Submit `open Calculator`; no app before approval; native dialog appears only after browser approval.
- [ ] Cancel/close/Escape/Return in native dialog causes no execution. Allow once launches Calculator once.
- [ ] Pending native dialog disappears after two minutes or Pause in browser. No later dispatch occurs.
- [ ] Confirm repeated/expired IDs fail. New request invalidates an older approval.
- [ ] Open Notepad, Paint, File Explorer, Settings, installed Chrome/Brave/Edge/Spotify. Missing installs report failure, with no fallback executable.
- [ ] Search YouTube for Sidemen, Spotify for Hindi songs and Maps for Delhi. Verify browser selection, encoded URL and no automatic login/playback claim.
- [ ] Liked songs opens the expected Spotify page; sign-in/playback remains manual.
- [ ] Media keys affect active player; confirm toggle wording and no claim to know playing state.
- [ ] Configure a locally installed Ollama model; Ask AI requires disclosure, returns text, executes nothing.
- [ ] Test invalid provider, disconnected network and provider timeout; no credentials in UI error or logs.
- [ ] Keyboard navigation, mobile-width layout, persona switching, editable shortcuts, reset preferences, clear activity.
- [ ] Run tests on Windows and build the PyInstaller folder; launch built executable without Python installed on a clean VM.
- [ ] Inspect CPU/RAM at idle, during native dialog and optional model use. Record measurements before performance claims.

Test results must distinguish automated mocks from manual integration. No installer/signature/real Windows smoke result is claimed until this checklist is performed.
