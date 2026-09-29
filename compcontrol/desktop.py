"""Native Tk command window. No HTTP server, webview, or browser UI at startup."""
import queue
import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

from .broker import Broker, BrokerError, DemoExecutor
from .providers import ProviderConfig, ProviderError, TextProvider
from .hotkey import SummonHotkey
from . import __version__
from .provider_presets import PRESETS, preset_for, config_from_fields

BG = '#161923'
PANEL = '#222635'
FG = '#f0f2f8'
MUTED = '#b8bed1'
ACCENT = '#b6a6ff'


class DesktopApp:
    def __init__(self, root, *, demo=False, broker=None, provider=None, hotkey=True, widget=False):
        self.root, self.demo = root, demo
        self.closed = False
        self.pending = None
        self.revision = 0
        self.ai_busy = False
        self.modal_active = False
        self.mailbox = queue.Queue()
        self.settings_window = None
        self.app_picker = None
        self.workspace_window = None
        self.discovery_busy = False
        self.discovery_mailbox = queue.Queue()
        self.executable_mailbox = queue.Queue()
        if broker is None:
            if demo:
                executor = DemoExecutor()
            else:
                from .actions import WindowsExecutor
                from .consent import native_confirm
                executor = WindowsExecutor(consent=lambda title, detail, valid:
                                           native_confirm(title, detail, valid, parent=root))
            broker = Broker(executor, demo=demo)
        self.broker = broker
        config_error = None
        try:
            self.provider = TextProvider(ProviderConfig()) if demo else (provider or TextProvider(ProviderConfig.from_env()))
        except ProviderError as exc:
            self.provider = TextProvider(ProviderConfig())
            config_error = str(exc)
        root.title(f'CompControl {__version__} · Native desktop')
        root.geometry('740x700')
        root.minsize(600, 650)
        root.configure(bg=BG)
        root.protocol('WM_DELETE_WINDOW', self.close)
        root.option_add('*Font', ('Segoe UI', 10))
        self._style()
        self.request = tk.StringVar()
        self.browser = tk.StringVar(value='default')
        self.persona = tk.StringVar(value='Jarvis')
        self.pin = tk.BooleanVar(value=False)
        self.compact = tk.BooleanVar(value=False)
        self.auto_ai = tk.BooleanVar(value=True)
        self.status = tk.StringVar(value='Demo · desktop effects and AI disabled' if demo else 'Local skills ready · AI off')
        self.title = tk.StringVar(value='What can I help you do?')
        self.approval_status = tk.StringVar(value='Nothing runs just because you type it.')
        self._build()
        self.request.trace_add('write', self._changed)
        self.browser.trace_add('write', self._changed)
        self.persona.trace_add('write', lambda *_: root.title(f'CompControl {__version__} · Native · ' + self.persona.get()))
        root.bind('<Return>', self._enter)
        root.bind('<Control-l>', lambda _: self.focus_request())
        root.bind('<Escape>', lambda _: self.cancel())
        root.bind_all('<Control-period>', lambda _: self.pause(force=True))
        self.hotkey = SummonHotkey(root, self.summon) if hotkey else None
        self.footer.configure(text=(self.hotkey.status if self.hotkey else 'Ctrl+L focuses the request') +
                              '  ·  Esc cancels  ·  Ctrl+. pauses')
        self._provider_status()
        self._text('Open apps, find music and videos, or calculate something.\n\n'
                   'Try “open a YouTube tab and find Sidemen videos”.\n'
                   'Unfamiliar wording? Use Interpret with AI. You still approve the exact action.')
        if config_error:
            self.status.set('AI configuration needs attention · open AI settings')
            self._text(config_error)
        self.timer = root.after(100, self._tick)
        if widget:
            self.compact.set(True)
            self.pin.set(True)
            self._compact()
            self._pin()
        root.after_idle(self.focus_request)

    def _style(self):
        style = ttk.Style(self.root)
        style.theme_use('clam')
        style.configure('TCombobox', fieldbackground=PANEL, background=PANEL, foreground=FG,
                        arrowcolor=FG, bordercolor=PANEL, padding=5)
        style.map('TCombobox', fieldbackground=[('readonly', PANEL)],
                  foreground=[('readonly', FG)], selectbackground=[('readonly', PANEL)])
        self.root.option_add('*TCombobox*Listbox.background', PANEL)
        self.root.option_add('*TCombobox*Listbox.foreground', FG)

    def _button(self, parent, text, command, primary=False):
        return tk.Button(parent, text=text, command=command, relief='flat', bd=0,
                         bg=ACCENT if primary else PANEL, fg='#171324' if primary else FG,
                         activebackground='#c8bcff' if primary else '#333a50',
                         activeforeground='#171324' if primary else FG, disabledforeground='#777e94',
                         padx=12, pady=6, cursor='hand2', highlightthickness=1,
                         highlightbackground=PANEL, highlightcolor=ACCENT)

    def _label(self, parent, text='', **kwargs):
        return tk.Label(parent, text=text, bg=BG, fg=MUTED, anchor='w', **kwargs)

    def _build(self):
        shell = tk.Frame(self.root, bg=BG, padx=24, pady=16)
        shell.pack(fill='both', expand=True)
        header = tk.Frame(shell, bg=BG)
        header.pack(fill='x')
        self._label(header, 'CompControl', font=('Segoe UI', 18, 'bold')).pack(side='left')
        self._button(header, 'AI settings', self.settings).pack(side='right')
        self._label(shell, 'YOUR DESKTOP, WITH YOU IN CONTROL', font=('Segoe UI', 9)).pack(fill='x', pady=(0, 10))
        options = tk.Frame(shell, bg=BG)
        options.pack(fill='x')
        for var, values, width in ((self.persona, ['Jarvis', 'Friday'], 8),
                                    (self.browser, ['default', 'chrome', 'brave', 'edge'], 9)):
            ttk.Combobox(options, textvariable=var, values=values, width=width, state='readonly').pack(side='left', padx=(0, 8))
        for text, var, command in (('Pin on top', self.pin, self._pin), ('Widget', self.compact, self._compact)):
            tk.Checkbutton(options, text=text, variable=var, command=command, bg=BG, fg=MUTED,
                           selectcolor=PANEL, activebackground=BG, activeforeground=FG).pack(side='left')
        self._label(shell, 'What would you like to do?').pack(fill='x', pady=(12, 5))
        self.entry = tk.Entry(shell, textvariable=self.request, bg=PANEL, fg=FG, insertbackground=ACCENT,
                              relief='flat', font=('Segoe UI', 13), highlightthickness=1,
                              highlightcolor=ACCENT, highlightbackground='#363d52')
        self.entry.pack(fill='x', ipady=10)
        row = tk.Frame(shell, bg=BG)
        row.pack(fill='x', pady=(8, 0))
        self._button(row, 'Plan request', self.plan, primary=True).pack(side='left')
        self.ai_button = self._button(row, 'Interpret with AI', self.interpret)
        self.ai_button.pack(side='left', padx=8)
        self.pause_button = self._button(row, 'Pause', self.pause)
        self.pause_button.pack(side='right')
        self.auto_check = tk.Checkbutton(shell, text='Offer AI interpretation when a local skill does not match',
                                         variable=self.auto_ai, bg=BG, fg=MUTED, selectcolor=PANEL,
                                         activebackground=BG, activeforeground=FG)
        self.auto_check.pack(anchor='w', pady=(4, 0))
        self.shortcuts = tk.Frame(shell, bg=BG)
        self.shortcuts.pack(fill='x', pady=(8, 0))
        for name, command in [('Calculator', 'open calculator'), ('YouTube', 'open a YouTube tab and find Sidemen videos'),
                              ('Spotify', 'open Spotify and play sad Hindi songs'), ('Skills', 'help')]:
            self._button(self.shortcuts, name, lambda c=command: self.shortcut(c)).pack(side='left', padx=(0, 6))
        tools = tk.Frame(shell, bg=BG)
        tools.pack(fill='x', pady=(8, 0))
        self._button(tools, 'Discover apps', self.discover_apps).pack(side='left')
        self._button(tools, 'Project files', self.project_files).pack(side='left', padx=8)
        # Reserve footer space first; the scrollable card gets the remaining height.
        self.footer = self._label(shell, font=('Segoe UI', 9), wraplength=540)
        self.footer.pack(side='bottom', fill='x', pady=(6, 0))
        self._label(shell, textvariable=self.status, wraplength=540, font=('Segoe UI', 9)).pack(side='bottom', fill='x')
        self.card = tk.Frame(shell, bg=PANEL, padx=16, pady=12)
        self.card.pack(fill='both', expand=True, pady=(12, 10))
        tk.Label(self.card, textvariable=self.title, font=('Segoe UI', 14, 'bold'),
                 bg=PANEL, fg=FG, anchor='w', wraplength=490).pack(side='top', fill='x')

        # Pack the bottom elements first so they are never pushed off-screen
        action_row = tk.Frame(self.card, bg=PANEL)
        action_row.pack(side='bottom', fill='x')
        tk.Label(self.card, textvariable=self.approval_status, bg=PANEL, fg=MUTED,
                 anchor='w', wraplength=490, font=('Segoe UI', 9)).pack(side='bottom', fill='x', pady=(8, 6))

        content = tk.Frame(self.card, bg=PANEL)
        content.pack(side='top', fill='both', expand=True, pady=(10, 0))
        self.output = tk.Text(content, bg=PANEL, fg=FG, relief='flat', wrap='word',
                              height=4, font=('Segoe UI', 11), state='disabled', cursor='arrow')
        scroll = ttk.Scrollbar(content, command=self.output.yview)
        self.output.configure(yscrollcommand=scroll.set)
        scroll.pack(side='right', fill='y')
        self.output.pack(side='left', fill='both', expand=True)

        self.review_button = self._button(action_row, 'Review & approve…', self.confirm, primary=True)
        self.review_button.pack(side='left')
        self.review_button.configure(state='disabled')
        self._button(action_row, 'Cancel', self.cancel).pack(side='left', padx=8)
        self._button(action_row, 'Activity', self.activity).pack(side='right')

    def _text(self, value):
        self.output.configure(state='normal')
        self.output.delete('1.0', 'end')
        self.output.insert('1.0', value)
        self.output.configure(state='disabled')

    def _changed(self, *_):
        self.revision += 1
        self.broker.invalidate()
        self.pending = None
        self.review_button.configure(state='disabled')
        self.approval_status.set('Request changed · prepare a new plan before approving.')

    def _enter(self, event):
        # Enter in the input plans only. It never approves an action.
        if event.widget == self.entry:
            self.plan()
            return 'break'

    def focus_request(self):
        self.entry.focus_set()
        self.entry.selection_range(0, 'end')

    def summon(self):
        modal = self.root.grab_current()
        if modal is not None:
            modal.lift()
            return
        self.root.deiconify()
        self.root.lift()
        self.focus_request()

    def _pin(self):
        self.root.attributes('-topmost', self.pin.get())

    def _compact(self):
        if self.compact.get():
            self.shortcuts.pack_forget()
            self.auto_check.pack_forget()
            self.root.minsize(600, 540)
            self.root.geometry('620x560')
        else:
            self.auto_check.pack(before=self.card, anchor='w', pady=(4, 0))
            self.shortcuts.pack(before=self.card, fill='x', pady=(8, 0))
            self.root.minsize(600, 650)
            self.root.geometry('740x700')

    def shortcut(self, command):
        self.request.set(command)
        self.plan()

    def plan(self):
        if self.modal_active:
            return
        self.revision += 1
        try:
            result = self.broker.plan(self.request.get(), self.browser.get())
            self.show_plan(result)
            if (result['title'] == 'Let’s interpret that' and self.auto_ai.get()
                    and self.provider.config.kind != 'off' and not self.demo):
                self.interpret()
        except ValueError as exc:
            self.error(str(exc))

    def show_plan(self, result):
        self.pending = result['approval_id']
        prefix = 'AI proposal · ' if result['source'] == 'ai' and self.pending else ''
        self.title.set(prefix + result['title'])
        detail = result['message']
        if result['actions']:
            a = result['actions'][0]
            detail += '\n\nExact action: ' + a['kind'] + ' / ' + a['target']
            if a['query']:
                detail += '\nSearch terms: ' + a['query']
            detail += '\nDestination: ' + '\n'.join(result['destinations'])
            detail += '\nBrowser: ' + a['browser']
        if result.get('intent'):
            detail += '\n\nLocal follow-up: ' + result['intent']
            if result.get('query'):
                detail += '\nSuggested search (not a selected target): ' + result['query']
            self.follow_up_query = result.get('query', '') if result['intent'] == 'find_app' else ''
        self._text(detail)
        self.review_button.configure(state='normal' if self.pending else 'disabled')
        self.approval_status.set('One action · expires in 2 minutes · review before allowing' if self.pending else
                                 'No desktop action proposed. Nothing was executed.')

    def error(self, message):
        self._changed()
        self.title.set('Needs your attention')
        self._text(message)
        self.approval_status.set('Nothing new was dispatched. You can edit the request and try again.')

    def confirm(self):
        if not self.pending or self.modal_active:
            return
        token = self.pending
        self.pending = None
        self.review_button.configure(state='disabled')
        self.modal_active = True
        try:
            result = self.broker.confirm(token)
            if not self.closed:
                self.title.set(result['status'].capitalize())
                self._text(result['message'])
                self.approval_status.set('Approval consumed. Each new action needs a new review.')
        except BrokerError as exc:
            if not self.closed:
                self.error(str(exc))

        finally:
            self.modal_active = False

    def cancel(self):
        self._changed()
        self.title.set('Cancelled')
        self._text('Pending proposals and any in-flight AI result were discarded. An already dispatched action cannot be undone.')
        self.approval_status.set('No pending approval.')

    def pause(self, force=False):
        enabled = True if force else not self.broker.state()['paused']
        result = self.broker.pause(enabled)
        self.revision += 1
        self.pending = None
        self.review_button.configure(state='disabled')
        self.pause_button.configure(text='Resume' if enabled else 'Pause')
        self.title.set('Actions paused' if enabled else 'Actions resumed')
        self._text(result['message'])
        self.approval_status.set('No pending approval.')

    def interpret(self):
        if self.modal_active:
            return
        if self.demo:
            self.error('AI is disabled in demo mode. Configure it on your Windows desktop.')
            return
        if self.ai_busy:
            self.status.set('AI is still finishing the previous request. You can use local skills meanwhile.')
            return
        cfg = self.provider.config
        if cfg.kind == 'off':
            self.settings()
            return
        text = self.request.get()
        try:
            from .planner import clean
            text = clean(text)
            if not text:
                raise ValueError('Type a request first.')
        except ValueError as exc:
            self.error(str(exc))
            return
        disclosed_revision = self.revision
        cloud = cfg.kind == 'openai'
        self.modal_active = True
        try:
            approved = messagebox.askokcancel('Send this request to AI?',
            ('CLOUD · provider charges and retention may apply.\n' if cloud else 'LOCAL MODEL · no bundled inference engine.\n') +
            f'Provider: {cfg.base_url}\nModel: {cfg.model}\n\n'
            'Only this request and the capability instructions are sent. No history, files or screen content. '
            'Do not include secrets. AI proposes; it cannot approve or execute.\n\nRequest:\n' + text,
                parent=self.root, default='cancel')
        finally:
            self.modal_active = False
        if not approved:
            return
        if self.closed:
            return
        if disclosed_revision != self.revision or cfg is not self.provider.config:
            self.error('Request or provider changed during disclosure. Please review and send it again.')
            return
        try:
            ticket = self.broker.begin_interpretation()
        except BrokerError as exc:
            self.error(str(exc))
            return
        self.revision += 1
        revision = self.revision
        browser, provider = self.browser.get(), self.provider
        self.pending = None
        self.review_button.configure(state='disabled')
        self.ai_busy = True
        self.ai_button.configure(state='disabled')
        self.title.set('Interpreting your request…')
        self._text('You can keep using local skills. Editing, cancelling, or pausing discards this AI result.\n\n'
                   'A network request already sent cannot be recalled. No automatic retry is made.')
        self.approval_status.set('Waiting for AI · nothing is approved')
        self.status.set('AI request in progress · timeout 30 seconds')

        def work():
            try:
                plan = provider.propose(text, browser)
                self.mailbox.put((revision, ticket, plan, None))
            except (ProviderError, ValueError) as exc:
                self.mailbox.put((revision, ticket, None, str(exc)))
            except Exception:
                self.mailbox.put((revision, ticket, None, 'AI request failed. No action was taken.'))
        threading.Thread(target=work, daemon=True).start()

    def _tick(self):
        if self.closed:
            return
        try:
            revision, ticket, plan, error = self.mailbox.get_nowait()
        except queue.Empty:
            pass
        else:
            self.ai_busy = False
            self._provider_status()
            if revision == self.revision:
                if error:
                    self.error(error)
                else:
                    try:
                        self.show_plan(self.broker.complete_interpretation(ticket, plan))
                    except BrokerError as exc:
                        self.error(str(exc))
        try:
            picker, revision, token, error = self.executable_mailbox.get_nowait()
        except queue.Empty:
            pass
        else:
            self.discovery_busy = False
            if (not error and not self.closed and self.revision == revision
                    and picker.winfo_exists()):
                try:
                    self.show_plan(self.broker.select_app(token))
                    picker.destroy()
                except ValueError as exc:
                    self.error(str(exc))
            elif error and picker.winfo_exists():
                self.title.set('App selection needs attention')
                self.status.set(error)
        try:
            rows, scan_error, picker, render = self.discovery_mailbox.get_nowait()
        except queue.Empty:
            pass
        else:
            self.discovery_busy = False
            if picker.winfo_exists():
                render(rows, scan_error)
        if self.pending and self.broker.state()['pending_id'] != self.pending:
            self.pending = None
            self.review_button.configure(state='disabled')
            self.approval_status.set('Approval expired or revoked. Prepare a new plan to continue.')
        self.timer = self.root.after(100, self._tick)

    def _provider_status(self):
        cfg = self.provider.config
        self.ai_button.configure(state='disabled' if self.demo or self.ai_busy else 'normal')
        self.auto_check.configure(state='disabled' if self.demo else 'normal')
        self.status.set('DEMO · no desktop effects or AI' if self.demo else
                        'Local skills ready · AI off' if cfg.kind == 'off' else
                        f'AI configured · {cfg.model} · each request asks permission')

    def project_files(self):
        if self.modal_active:
            return
        if self.workspace_window is not None and self.workspace_window.winfo_exists():
            self.workspace_window.lift()
            return
        from .workspace_ui import open_workspace
        self.workspace_window = open_workspace(self)

    def discover_apps(self):
        if self.modal_active:
            return
        if self.demo:
            self.error('App discovery is disabled in demo mode. Use this on Windows.')
            return
        if self.app_picker is not None and self.app_picker.winfo_exists():
            self.app_picker.lift()
            return
        if self.discovery_busy:
            self.error('Wait for the previous local app scan to finish.')
            return
        catalog = getattr(self.broker.executor, 'catalog', None)
        if catalog is None:
            self.error('This executor does not provide Windows app discovery.')
            return
        self._changed()
        win = tk.Toplevel(self.root)
        self.app_picker = win
        win.title('Discover installed Windows apps · local only')
        win.geometry('720x560')
        win.minsize(540, 420)
        win.configure(bg=BG)
        win.transient(self.root)
        self._label(win, 'Reads Windows Start-menu names and AppIDs. Nothing is sent to AI. '
                    'Select the exact registration; discovery is not a publisher/security check.',
                    wraplength=640).pack(fill='x', padx=20, pady=12)
        query = tk.StringVar(value=getattr(self, 'follow_up_query', ''))
        tk.Entry(win, textvariable=query, bg=PANEL, fg=FG, insertbackground=FG).pack(fill='x', padx=20, ipady=6)
        listing = tk.Listbox(win, bg=PANEL, fg=FG, selectmode='browse', exportselection=False)
        listing.pack(fill='both', expand=True, padx=20, pady=10)
        detail = tk.StringVar(value='Choose Scan Start menu. Portable apps without a registration may not appear.')
        self._label(win, textvariable=detail, wraplength=640).pack(fill='x', padx=20, pady=8)
        rows, shown = [], []

        def filter_rows(*_):
            nonlocal shown
            # Name filtering is merely UI search. No first/best match is ever selected.
            shown = [(token, app) for token, app in rows if query.get().casefold() in app.name.casefold()]
            listing.delete(0, 'end')
            for _, app in shown:
                listing.insert('end', app.name + '  —  ' + app.app_id)
            choose.configure(state='disabled')

        def selected(_=None):
            indexes = listing.curselection()
            if indexes:
                detail.set(shown[indexes[0]][1].detail)
                choose.configure(state='normal')

        def render(result, error):
            nonlocal rows
            rows = result
            scan.configure(state='normal')
            filter_rows()
            detail.set(error or f'{len(rows)} registrations found. Select one; choices expire in 2 minutes.')

        def scan_apps():
            nonlocal rows
            if self.discovery_busy:
                return
            self._changed()
            rows = []
            filter_rows()
            self.discovery_busy = True
            scan.configure(state='disabled')
            detail.set('Reading Windows Start menu locally… you can cancel or pause in the main window.')
            def work():
                try:
                    result, error = catalog.scan(), None
                except Exception:
                    result, error = [], 'Windows app discovery failed or timed out. No launch occurred.'
                self.discovery_mailbox.put((result, error, win, render))
            threading.Thread(target=work, daemon=True).start()

        def select_app():
            indexes = listing.curselection()
            if not indexes:
                return
            try:
                token, target = shown[indexes[0]]
                if not target.packaged:
                    detail.set('Classic entry: select its trusted executable; shortcut arguments are never run.')
                    select_exe()
                    return
                self.show_plan(self.broker.select_app(token))
                win.destroy()
            except ValueError as exc:
                detail.set(str(exc))

        def select_exe():
            self._changed()
            revision = self.revision
            value = filedialog.askopenfilename(parent=win, title='Select a trusted local executable (no arguments)',
                                               filetypes=[('Windows executable', '*.exe')])
            if not value or revision != self.revision:
                return
            self.discovery_busy = True
            detail.set('Hashing selected executable locally… no code has been launched.')
            def work():
                try:
                    token, error = catalog.add_executable(value), None
                except Exception:
                    token, error = None, 'Executable selection failed. Nothing was launched.'
                self.executable_mailbox.put((win, revision, token, error))
            threading.Thread(target=work, daemon=True).start()

        buttons = tk.Frame(win, bg=BG)
        buttons.pack(fill='x', padx=20, pady=12)
        scan = self._button(buttons, 'Scan Start menu', scan_apps)
        scan.pack(side='left')
        self._button(buttons, 'Select .exe…', select_exe).pack(side='left', padx=8)
        choose = self._button(buttons, 'Prepare selected launch', select_app, primary=True)
        choose.pack(side='right')
        choose.configure(state='disabled')
        query.trace_add('write', filter_rows)
        listing.bind('<<ListboxSelect>>', selected)

    def settings(self):
        if self.modal_active:
            return
        if self.settings_window is not None and self.settings_window.winfo_exists():
            self.settings_window.lift()
            return
        win = tk.Toplevel(self.root)
        self.settings_window = win
        win.title('Cloud AI setup · CompControl')
        win.configure(bg=BG)
        win.geometry('620x650')
        win.minsize(560, 620)
        win.transient(self.root)
        body = tk.Frame(win, bg=BG, padx=24, pady=20)
        body.pack(fill='both', expand=True)
        self._label(body, 'Cloud AI · no local model needed', font=('Segoe UI', 16, 'bold')).pack(fill='x')
        self._label(body, 'Pick a provider, paste its API key, then test. Your laptop runs only the app. '
                    'No Ollama, GPU, Docker or provider SDK is needed for cloud APIs.',
                    wraplength=520).pack(fill='x', pady=(8, 12))
        cfg = self.provider.config
        label = tk.StringVar(value='Groq (cloud)' if cfg.kind == 'off' else preset_for(cfg))
        values = {key: tk.StringVar(value=getattr(cfg, key)) for key in ('base_url', 'model', 'api_key')}
        picker = ttk.Combobox(body, textvariable=label, values=list(PRESETS), state='readonly')
        picker.pack(fill='x')
        hint = self._label(body, wraplength=520)
        hint.pack(fill='x', pady=(6, 0))

        def choose(_=None):
            preset = PRESETS[label.get()]
            values['base_url'].set(preset.base_url)
            values['model'].set(preset.model)
            # Never carry one provider's credential into a different provider.
            values['api_key'].set('')
            hint.configure(text=preset.note)
        picker.bind('<<ComboboxSelected>>', choose)
        if cfg.kind == 'off':
            choose()
        else:
            hint.configure(text=PRESETS[label.get()].note)
        for key, title in [('base_url', 'API base URL (filled by the preset)'),
                           ('model', 'Text model ID (editable; must be available to your account)'),
                           ('api_key', 'API key (paste here, never in the request box)')]:
            self._label(body, title).pack(fill='x', pady=(10, 4))
            field = tk.Entry(body, textvariable=values[key], bg=PANEL, fg=FG, insertbackground=FG,
                             show='•' if key == 'api_key' else '', relief='flat')
            field.pack(fill='x', ipady=7)
        # Any endpoint edit, including paste, clears the previous credential.
        values['base_url'].trace_add('write', lambda *_: values['api_key'].set(''))
        info = self._label(body, 'Session only: keys/settings are not saved to disk. Presets do not guarantee '
                           'free usage. Check your account’s quota and pricing. No automatic provider fallback.', wraplength=520)
        info.pack(fill='x', pady=12)
        testing = False
        revision = 0
        replies = queue.Queue()
        timer = None

        def edited(*_):
            nonlocal revision
            revision += 1
        for var in [label, *values.values()]:
            var.trace_add('write', edited)

        def read_config():
            config = config_from_fields(label.get(), *(values[k].get() for k in ('base_url', 'model', 'api_key')))
            if config.kind == 'openai' and not config.api_key:
                raise ProviderError('Paste this provider’s API key before applying or testing.')
            return config

        def apply():
            if self.demo:
                info.configure(text='AI is disabled in demo mode. Launch Start CompControl.cmd on your Windows PC.')
                return
            if testing or self.ai_busy:
                info.configure(text='Wait for the current API request to finish before changing providers.')
                return
            try:
                self.provider = TextProvider(read_config())
            except ProviderError as exc:
                info.configure(text=str(exc))
                return
            self._changed()
            self._provider_status()
            self.title.set('AI setup applied')
            self._text('Type normally and select Plan request. If a local skill does not match, '
                       'the app will offer AI interpretation. You approve each transmission and each desktop action.')
            close()

        def poll_test():
            nonlocal testing, timer
            timer = None
            try:
                sent_revision, result = replies.get_nowait()
            except queue.Empty:
                timer = win.after(100, poll_test)
                return
            testing = False
            self.ai_busy = False
            self._provider_status()
            test_button.configure(state='normal')
            info.configure(text=result if revision == sent_revision else
                           'Settings changed during the test. Test the new settings before applying.')

        def test():
            nonlocal testing, timer
            if self.demo or self.ai_busy or testing:
                info.configure(text='Testing is disabled in demo mode or while another API request is running.')
                return
            try:
                config = read_config()
                if config.kind == 'off':
                    raise ProviderError('Choose a cloud provider to test AI. Local skills do not need a connection.')
            except ProviderError as exc:
                info.configure(text=str(exc))
                return
            sent_revision = revision
            self.modal_active = True
            try:
                consent = messagebox.askokcancel('Test this AI provider?',
                    f'Endpoint: {config.base_url}\nModel: {config.model}\n\n'
                    'Sends the fixed test “open calculator” plus capability instructions. '
                    'Uses your API quota and may cost money. No actual desktop action is planned or executed.',
                    parent=win, default='cancel')
            finally:
                self.modal_active = False
            if not consent or sent_revision != revision or self.closed:
                return
            self._changed()
            testing = True
            self.ai_busy = True
            self._provider_status()
            test_button.configure(state='disabled')
            info.configure(text='Testing API authentication and structured output… no desktop effects.')

            def worker():
                try:
                    plan = TextProvider(config).propose('open calculator')
                    from .models import Action
                    result = ('Test passed: provider returned the expected Calculator proposal. '
                              'Nothing executed. Select Apply for this session.' if plan.actions == (Action('app', 'calculator'),)
                              else 'Provider responded, but did not return the expected action. Try another text model.')
                except ProviderError as exc:
                    result = str(exc)
                except Exception:
                    result = 'API test failed. No action was taken. Check the endpoint and model.'
                replies.put((sent_revision, result))
            threading.Thread(target=worker, daemon=True).start()
            timer = win.after(100, poll_test)

        def close():
            if testing:
                info.configure(text='Wait for the API test to finish before closing this setup window.')
                return
            if timer is not None:
                win.after_cancel(timer)
            values['api_key'].set('')
            win.destroy()
        win.protocol('WM_DELETE_WINDOW', close)
        buttons = tk.Frame(body, bg=BG)
        buttons.pack(fill='x', pady=(8, 0))
        test_button = self._button(buttons, 'Test AI setup', test)
        test_button.pack(side='left')
        self._button(buttons, 'Apply for this session', apply, primary=True).pack(side='right')

    def activity(self):
        win = tk.Toplevel(self.root)
        win.title('Session activity · CompControl')
        win.geometry('500x400')
        win.configure(bg=BG)
        self._label(win, 'Action labels only · no prompts or search terms saved', wraplength=450).pack(padx=20, pady=16)
        text = tk.Text(win, bg=PANEL, fg=FG, wrap='word', relief='flat', height=12)
        text.pack(fill='both', expand=True, padx=20)
        events = self.broker.state()['activity']
        text.insert('1.0', '\n'.join(f"{e['time']}   {e['title']} — {e['status']}" for e in events) or 'No session activity yet.')
        text.configure(state='disabled')
        def clear():
            self.broker.clear()
            self.cancel()
            win.destroy()
        self._button(win, 'Clear activity & pending work', clear).pack(pady=16)

    def close(self):
        if self.closed:
            return
        self.closed = True
        self.broker.pause(True)
        self.revision += 1
        self.root.after_cancel(self.timer)
        if self.hotkey:
            self.hotkey.close()
        self.root.destroy()


def run_desktop(demo=False, widget=False):
    # Best effort: crisp text at Windows scaling without requiring elevation.
    import platform
    if platform.system() == 'Windows':
        import ctypes
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except (OSError, AttributeError):
            pass
    try:
        root = tk.Tk()
    except tk.TclError as exc:
        raise ValueError('A desktop display and Python Tcl/Tk support are required. Use --cli or --web --demo here.') from exc
    try:
        DesktopApp(root, demo=demo, widget=widget)
        root.mainloop()
    except tk.TclError as exc:
        raise ValueError('The native window could not initialize. Verify Python Tcl/Tk and display support.') from exc
    finally:
        try:
            root.destroy()
        except tk.TclError:
            pass
