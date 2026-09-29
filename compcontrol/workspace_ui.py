"""Native local-only file review workflow. No provider, original-file writes or apply."""
import tkinter as tk
from tkinter import filedialog
from pathlib import Path

from .file_workspace import snapshot, preview_replace, export_patch, WorkspaceError


def open_workspace(app):
    if app.demo:
        app.error('Project file access is disabled in demo mode. Use the native Windows app.')
        return
    app.cancel()
    win = tk.Toplevel(app.root)
    win.title('Project files · review a patch, never modify originals')
    win.geometry('860x760')
    win.minsize(620, 600)
    win.transient(app.root)
    selected = None
    preview = None
    project = None
    status = tk.StringVar(value='Select a project, then one exact file. Nothing is sent to AI.')
    tk.Label(win, textvariable=status, wraplength=780, justify='left').pack(fill='x', padx=16, pady=12)
    row = tk.Frame(win)
    row.pack(fill='x', padx=16)
    fields = tk.Frame(win)
    fields.pack(fill='x', padx=16, pady=8)
    tk.Label(fields, text='Exact text to replace (must match once)').pack(anchor='w')
    old = tk.Text(fields, height=3, wrap='none')
    old.pack(fill='x')
    tk.Label(fields, text='Replacement (empty removes only that exact text in the exported patch)').pack(anchor='w')
    new = tk.Text(fields, height=3, wrap='none')
    new.pack(fill='x')
    controls = tk.Frame(win)
    controls.pack(fill='x', padx=16, pady=8)
    body = tk.Frame(win)
    body.pack(fill='both', expand=True, padx=16, pady=(0, 16))
    output = tk.Text(body, wrap='none', state='disabled')
    scrollbar = tk.Scrollbar(body, command=output.yview)
    output.configure(yscrollcommand=scrollbar.set)
    scrollbar.pack(side='right', fill='y')
    horizontal = tk.Scrollbar(body, orient='horizontal', command=output.xview)
    output.configure(xscrollcommand=horizontal.set)
    horizontal.pack(side='bottom', fill='x')
    output.pack(fill='both', expand=True)

    def show(value):
        output.configure(state='normal')
        output.delete('1.0', 'end')
        output.insert('1.0', value)
        output.configure(state='disabled')

    def revoke(_=None):
        nonlocal preview
        if preview is not None:
            app._changed()
        preview = None
        save.configure(state='disabled')
        for field in (old, new):
            if field.edit_modified():
                field.edit_modified(False)

    def choose_project():
        nonlocal project, selected
        revoke()
        selected = None
        value = filedialog.askdirectory(parent=win, title='Select the project root (not your whole drive)')
        project = Path(value) if value else None
        status.set('Project: ' + str(project) if project else 'Project selection cancelled.')
        show('Now choose the exact file. No directory indexing or AI upload occurs.')

    def choose_file():
        nonlocal selected
        revoke()
        selected = None
        if project is None:
            status.set('Choose the project root first.')
            return
        value = filedialog.askopenfilename(parent=win, initialdir=str(project), title='Choose one UTF-8 project file')
        if not value:
            return
        try:
            relative = Path(value).relative_to(project).as_posix()
            selected = snapshot(project, relative)
            status.set('Selected exact file. Enter a unique replacement, then preview.')
            # repr exposes embedded controls rather than visually concealing them.
            show(selected.detail + '\n\nSource (escaped view; copy original text from your editor):\n' +
                 repr(selected.data.decode('utf-8')))
        except (ValueError, OSError) as exc:
            status.set(str(exc) if isinstance(exc, WorkspaceError) else 'Choose a file inside the selected project.')
            show('No file selected. Nothing was modified.')

    def make_preview():
        nonlocal preview
        revoke()
        if selected is None:
            status.set('Select a project and exact file first.')
            return
        try:
            preview = preview_replace(selected, old.get('1.0', 'end-1c'), new.get('1.0', 'end-1c'))
            # Escape hidden direction/control chars; preserve patch layout.
            import unicodedata
            text = preview.patch.decode('utf-8')
            safe = ''.join(c if c in '\n\r\t' or unicodedata.category(c) not in {'Cc', 'Cf'}
                           else ascii(c)[1:-1] for c in text)
            show(safe)
            save.configure(state='normal')
            status.set('Review the diff. Export creates only a NEW .patch outside the project; it does NOT apply it.')
        except WorkspaceError as exc:
            status.set(str(exc))
            show('Preview unavailable. Original unchanged.')

    def save_patch():
        nonlocal preview
        if preview is None:
            return
        reviewed = preview
        if app.broker.state()['paused']:
            status.set('Actions are paused. Resume before preparing an export approval.')
            return
        # Revoke any earlier desktop approval before the save dialog.
        app._changed()
        revision = app.revision
        import time
        expires = time.monotonic() + 120
        valid = lambda: (not app.closed and app.revision == revision and preview is reviewed
                         and win.winfo_exists() and not app.broker.state()['paused']
                         and time.monotonic() < expires)
        value = filedialog.asksaveasfilename(parent=win, title='Choose a NEW patch file outside the project',
                                             defaultextension='.patch', filetypes=[('Patch', '*.patch')])
        if not value or not valid():
            return
        try:
            executor = app.broker.executor
            patch_catalog = getattr(executor, 'patch_catalog', None)
            if patch_catalog is None:
                raise WorkspaceError('The current executor cannot export reviewed patches.')
            token = patch_catalog.register(reviewed, value)
            if not valid():
                return
            result = app.broker.offer_patch_export(token)
            app.show_plan(result)
            status.set('Patch target prepared. Review the full path/hash in the main window, then use Review & approve. The original remains unchanged.')
            win.destroy()
        except (WorkspaceError, ValueError) as exc:
            status.set(str(exc))

    tk.Button(row, text='1. Select project', command=choose_project).pack(side='left')
    tk.Button(row, text='2. Select exact file', command=choose_file).pack(side='left', padx=8)
    tk.Button(controls, text='3. Preview patch', command=make_preview).pack(side='left')
    save = tk.Button(controls, text='4. Export new patch…', command=save_patch, state='disabled')
    save.pack(side='left', padx=8)
    for field in (old, new):
        field.bind('<<Modified>>', revoke)
    show('This is a local manual change-preview tool, not an autonomous coding agent.\n'
         'UTF-8 files up to 256 KiB; links/reparse points/hardlinks are not supported.\n'
         'An exact file selection is required even when filenames are similar.')

    return win
