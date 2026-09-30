"""Native Tk Autonomous Command Center & HUD. Lightweight stdlib + Tcl/Tk runtime."""
import json
import os
import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from . import __version__
from .actions import collect_system_telemetry
from .broker import Broker, BrokerError, DemoExecutor
from .hotkey import SummonHotkey
from .provider_presets import PRESETS, config_from_fields, preset_for
from .providers import ProviderConfig, ProviderError, TextProvider

BG = '#0B0E14'
SURFACE = '#111622'
PANEL = '#161D2B'
PANEL_HOVER = '#1F293D'
BORDER = '#263147'
FG = '#F8FAFC'
MUTED = '#94A3B8'
ACCENT = '#6366F1'
ACCENT_FG = '#FFFFFF'
SUCCESS = '#10B981'
DANGER = '#F43F5E'

CONFIG_PATH = Path.home() / '.compcontrol_ai.json'


def load_saved_provider_config() -> ProviderConfig | None:
    """Load user-saved provider config if present and valid."""
    try:
        if not CONFIG_PATH.is_file():
            return None
        data = json.loads(CONFIG_PATH.read_text(encoding='utf-8'))
        cfg = ProviderConfig(
            kind=data.get('kind', 'off'),
            base_url=data.get('base_url', ''),
            model=data.get('model', ''),
            api_key=data.get('api_key', ''),
        )
        cfg.validate()
        return cfg if cfg.kind != 'off' else None
    except Exception:
        return None


def save_provider_config(cfg: ProviderConfig) -> None:
    """Save provider config to user home with 0600 permissions."""
    try:
        if cfg.kind == 'off':
            if CONFIG_PATH.is_file():
                CONFIG_PATH.unlink()
            return
        payload = json.dumps({
            'kind': cfg.kind,
            'base_url': cfg.base_url,
            'model': cfg.model,
            'api_key': cfg.api_key,
        })
        flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
        fd = os.open(CONFIG_PATH, flags, 0o600)
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write(payload)
    except OSError:
        pass


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
        self.command_history = []
        self.history_index = -1

        if broker is None:
            if demo:
                executor = DemoExecutor()
            else:
                from .actions import WindowsExecutor
                from .consent import native_confirm
                executor = WindowsExecutor(
                    consent=lambda title, detail, valid: native_confirm(title, detail, valid, parent=root)
                )
            broker = Broker(executor, demo=demo)
        self.broker = broker

        config_error = None
        try:
            if demo:
                self.provider = TextProvider(ProviderConfig())
            elif provider is not None:
                self.provider = provider
            else:
                env_cfg = ProviderConfig.from_env()
                if env_cfg.kind != 'off':
                    self.provider = TextProvider(env_cfg)
                else:
                    saved_cfg = load_saved_provider_config()
                    self.provider = TextProvider(saved_cfg or ProviderConfig())
        except ProviderError as exc:
            self.provider = TextProvider(ProviderConfig())
            config_error = str(exc)

        root.title(f'CompControl {__version__} · Autonomous Desktop Agent')
        root.geometry('820x720')
        root.minsize(640, 620)
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
        self.auto_approve = tk.BooleanVar(value=True)
        self.status = tk.StringVar(
            value='Demo · simulation mode' if demo else 'Autonomous engine ready · Exploit Shield active'
        )
        self.title = tk.StringVar(value='Ready for your command')
        self.approval_status = tk.StringVar(value='⚡ Auto-Approve active · safe tasks execute immediately')

        self._build()
        self.request.trace_add('write', self._changed)
        self.browser.trace_add('write', self._changed)
        self.persona.trace_add('write', lambda *_: root.title(f'CompControl {__version__} · ' + self.persona.get()))

        root.bind('<Return>', self._enter)
        root.bind('<Control-l>', lambda _: self.focus_request())
        root.bind('<Control-k>', lambda _: self.focus_request())
        root.bind('<Escape>', lambda _: self.cancel())
        root.bind_all('<Control-period>', lambda _: self.pause(force=True))
        self.entry.bind('<Up>', self._history_up)
        self.entry.bind('<Down>', self._history_down)

        self.hotkey = SummonHotkey(root, self.summon) if hotkey else None
        self.footer.configure(
            text=(self.hotkey.status if self.hotkey else 'Ctrl+L / Ctrl+K focuses command bar')
            + '  ·  Enter executes  ·  Up/Down history  ·  Esc cancels  ·  Ctrl+. pauses'
        )
        self._provider_status()
        self._text(
            '⚡ Zero-Friction Autonomous Mode is active.\n\n'
            '• Type any command and press Enter to execute immediately:\n'
            '  "play my liked songs list"  |  "open Visual Studio Code"  |  "install VLC"\n'
            '  "open yt and search for Sidemen"  |  "system info"  |  "open downloads"\n\n'
            '• Safe everyday actions run in 1 click without nagging popups.\n'
            '• Destructive shell commands are guarded by CompControl Exploit Shield.'
        )
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
        style.configure(
            'TCombobox',
            fieldbackground=PANEL,
            background=PANEL,
            foreground=FG,
            arrowcolor=FG,
            bordercolor=BORDER,
            padding=5,
        )
        style.map(
            'TCombobox',
            fieldbackground=[('readonly', PANEL)],
            foreground=[('readonly', FG)],
            selectbackground=[('readonly', PANEL)],
        )
        self.root.option_add('*TCombobox*Listbox.background', PANEL)
        self.root.option_add('*TCombobox*Listbox.foreground', FG)

    def _button(self, parent, text, command, primary=False, danger=False, subtle=False):
        bg = DANGER if danger else (ACCENT if primary else (SURFACE if subtle else PANEL))
        fg = ACCENT_FG if (primary or danger) else (MUTED if subtle else FG)
        active_bg = '#E11D48' if danger else ('#818CF8' if primary else PANEL_HOVER)
        return tk.Button(
            parent,
            text=text,
            command=command,
            relief='flat',
            bd=0,
            bg=bg,
            fg=fg,
            activebackground=active_bg,
            activeforeground=ACCENT_FG if (primary or danger) else FG,
            disabledforeground='#475569',
            padx=12 if not subtle else 9,
            pady=6 if not subtle else 4,
            cursor='hand2',
            font=('Segoe UI', 9, 'bold' if primary else 'normal'),
            highlightthickness=1,
            highlightbackground=BORDER if not primary else ACCENT,
            highlightcolor=ACCENT,
        )

    def _label(self, parent, text='', **kwargs):
        bg = kwargs.pop('bg', BG)
        fg = kwargs.pop('fg', MUTED)
        return tk.Label(parent, text=text, bg=bg, fg=fg, anchor='w', **kwargs)

    def _build(self):
        shell = tk.Frame(self.root, bg=BG, padx=22, pady=16)
        shell.pack(fill='both', expand=True)

        # Top Header
        header = tk.Frame(shell, bg=BG)
        header.pack(fill='x')
        brand_row = tk.Frame(header, bg=BG)
        brand_row.pack(side='left')
        self._label(brand_row, '⚡ CompControl', fg=FG, font=('Segoe UI', 17, 'bold')).pack(side='left')
        self._label(
            brand_row,
            f'  v{__version__} · AUTONOMOUS AGENT',
            fg=ACCENT,
            font=('Segoe UI', 8, 'bold'),
        ).pack(side='left', pady=(4, 0))

        header_btns = tk.Frame(header, bg=BG)
        header_btns.pack(side='right')
        self.pause_button = self._button(header_btns, 'Pause', self.pause)
        self.pause_button.pack(side='right', padx=(6, 0))
        self._button(header_btns, 'Activity', self.activity).pack(side='right', padx=(6, 0))
        self._button(header_btns, '⚙ AI Settings', self.settings, primary=True).pack(side='right')

        # Mode & Toggle Bar
        options = tk.Frame(shell, bg=SURFACE, padx=10, pady=6, highlightthickness=1, highlightbackground=BORDER)
        options.pack(fill='x', pady=(10, 10))
        for var, values, width in (
            (self.persona, ['Jarvis', 'Friday'], 8),
            (self.browser, ['default', 'chrome', 'brave', 'edge'], 9),
        ):
            ttk.Combobox(options, textvariable=var, values=values, width=width, state='readonly').pack(
                side='left', padx=(0, 8)
            )
        for text, var, command in (
            ('⚡ Auto-Approve', self.auto_approve, self._update_auto_approve_label),
            ('🧠 Auto-AI', self.auto_ai, None),
            ('📌 Pin', self.pin, self._pin),
            ('🗖 HUD', self.compact, self._compact),
        ):
            cb = tk.Checkbutton(
                options,
                text=text,
                variable=var,
                command=command,
                bg=SURFACE,
                fg=FG if 'Auto' in text else MUTED,
                selectcolor=PANEL,
                activebackground=SURFACE,
                activeforeground=FG,
                font=('Segoe UI', 9),
            )
            cb.pack(side='left', padx=(2, 6))
            if text == '🧠 Auto-AI':
                self.auto_check = cb

        # Command Composer Bar
        composer_label = tk.Frame(shell, bg=BG)
        composer_label.pack(fill='x', pady=(2, 4))
        self._label(
            composer_label,
            'COMMAND BAR  ·  Type naturally & press Enter',
            fg=MUTED,
            font=('Segoe UI', 8, 'bold'),
        ).pack(side='left')

        composer_frame = tk.Frame(shell, bg=PANEL, highlightthickness=2, highlightbackground=BORDER, highlightcolor=ACCENT)
        composer_frame.pack(fill='x')
        tk.Label(composer_frame, text='›', bg=PANEL, fg=ACCENT, font=('Consolas', 16, 'bold'), padx=10).pack(side='left')
        self.entry = tk.Entry(
            composer_frame,
            textvariable=self.request,
            bg=PANEL,
            fg=FG,
            insertbackground=ACCENT,
            relief='flat',
            font=('Segoe UI', 13),
            bd=0,
        )
        self.entry.pack(side='left', fill='x', expand=True, ipady=10, padx=(0, 8))

        # Primary Action Controls Row
        row = tk.Frame(shell, bg=BG)
        row.pack(fill='x', pady=(8, 0))
        self._button(row, '⚡ Execute / Plan', self.plan, primary=True).pack(side='left')
        self.ai_button = self._button(row, '✧ Interpret with AI', self.interpret)
        self.ai_button.pack(side='left', padx=8)
        self._button(row, '🔍 Discover Apps', self.discover_apps).pack(side='left')
        self._button(row, '📁 Project Files', self.project_files).pack(side='left', padx=8)

        # Quick-Action Dock (1-Click Pills)
        self.shortcuts = tk.Frame(shell, bg=BG)
        self.shortcuts.pack(fill='x', pady=(10, 0))
        quick_actions = [
            ('🎵 Liked Songs', 'play my liked songs list'),
            ('⏯ Play/Pause', 'toggle playback'),
            ('🔊 Vol+', 'volume up'),
            ('🔉 Vol-', 'volume down'),
            ('🔇 Mute', 'mute'),
            ('💻 VS Code', 'open Visual Studio Code'),
            ('▶ YouTube', 'open a YouTube tab and find Sidemen videos'),
            ('🎧 Spotify', 'open Spotify and play sad Hindi songs'),
            ('🧮 Calc', 'open calculator'),
            ('📊 System Info', 'system info'),
            ('📂 Downloads', 'open downloads'),
        ]
        for name, command in quick_actions:
            self._button(self.shortcuts, name, lambda c=command: self.shortcut(c), subtle=True).pack(
                side='left', padx=(0, 4), pady=2
            )

        # Reserve Footer Space
        self.footer = self._label(shell, font=('Segoe UI', 8), wraplength=760)
        self.footer.pack(side='bottom', fill='x', pady=(6, 0))
        self._label(shell, textvariable=self.status, wraplength=760, font=('Segoe UI', 9), fg=SUCCESS).pack(
            side='bottom', fill='x'
        )

        # Output & Execution Card
        self.card = tk.Frame(shell, bg=SURFACE, padx=16, pady=12, highlightthickness=1, highlightbackground=BORDER)
        self.card.pack(fill='both', expand=True, pady=(10, 8))

        tk.Label(
            self.card,
            textvariable=self.title,
            font=('Segoe UI', 13, 'bold'),
            bg=SURFACE,
            fg=FG,
            anchor='w',
            wraplength=720,
        ).pack(side='top', fill='x')

        action_row = tk.Frame(self.card, bg=SURFACE)
        action_row.pack(side='bottom', fill='x')
        tk.Label(
            self.card,
            textvariable=self.approval_status,
            bg=SURFACE,
            fg=MUTED,
            anchor='w',
            wraplength=720,
            font=('Segoe UI', 9),
        ).pack(side='bottom', fill='x', pady=(8, 6))

        content = tk.Frame(self.card, bg=PANEL, highlightthickness=1, highlightbackground=BORDER)
        content.pack(side='top', fill='both', expand=True, pady=(8, 0))
        self.output = tk.Text(
            content,
            bg=PANEL,
            fg=FG,
            relief='flat',
            wrap='word',
            height=5,
            font=('Consolas', 10),
            padx=12,
            pady=10,
            state='disabled',
            cursor='arrow',
        )
        scroll = ttk.Scrollbar(content, command=self.output.yview)
        self.output.configure(yscrollcommand=scroll.set)
        scroll.pack(side='right', fill='y')
        self.output.pack(side='left', fill='both', expand=True)

        self.review_button = self._button(action_row, 'Approve & Run Now ⚡', self.confirm, primary=True)
        self.review_button.pack(side='left')
        self.review_button.configure(state='disabled')
        self._button(action_row, 'Cancel (Esc)', self.cancel).pack(side='left', padx=8)
        self._button(action_row, 'Clear Output', lambda: self._text('Ready.')).pack(side='right')

    def _update_auto_approve_label(self):
        if self.auto_approve.get():
            self.approval_status.set('⚡ Auto-Approve active · safe tasks execute immediately')
        else:
            self.approval_status.set('Manual review mode · click Approve & Run Now before execution')

    def _history_up(self, _event):
        if not self.command_history:
            return 'break'
        if self.history_index < len(self.command_history) - 1:
            self.history_index += 1
            self.request.set(self.command_history[self.history_index])
            self.entry.icursor('end')
        return 'break'

    def _history_down(self, _event):
        if self.history_index > 0:
            self.history_index -= 1
            self.request.set(self.command_history[self.history_index])
            self.entry.icursor('end')
        elif self.history_index == 0:
            self.history_index = -1
            self.request.set('')
        return 'break'

    def _record_history(self, cmd: str):
        cmd = cmd.strip()
        if cmd and (not self.command_history or self.command_history[0] != cmd):
            self.command_history.insert(0, cmd)
            if len(self.command_history) > 50:
                self.command_history.pop()
        self.history_index = -1

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
        if self.auto_approve.get():
            self.approval_status.set('⚡ Press Enter to execute immediately.')
        else:
            self.approval_status.set('Request changed · prepare a new plan before approving.')

    def _enter(self, event):
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
            self.root.minsize(560, 420)
            self.root.geometry('620x440')
        else:
            self.shortcuts.pack(before=self.card, fill='x', pady=(10, 0))
            self.root.minsize(640, 620)
            self.root.geometry('820x720')

    def shortcut(self, command):
        self.request.set(command)
        self.plan()

    def plan(self):
        if self.modal_active:
            return
        self.revision += 1
        raw = self.request.get()
        if raw.strip():
            self._record_history(raw)
        try:
            result = self.broker.plan(raw, self.browser.get())
            self.show_plan(result)
            if (result['title'] == 'Let’s interpret that' and self.auto_ai.get()
                    and self.provider.config.kind != 'off' and not self.demo):
                self.interpret()
                return
            # Auto-execute immediately if Auto-Approve is enabled in non-demo mode and no destructive popup is needed
            if (self.pending and self.auto_approve.get() and not self.demo
                    and not result.get('requires_popup', False)):
                self.confirm()
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
                detail += '\nSearch / Label: ' + a['query']
            detail += '\nDestination: ' + '\n'.join(result['destinations'])
            detail += '\nBrowser: ' + a['browser']
            if result.get('risk'):
                detail += '\nSecurity Tier: ' + result['risk'].upper()
        if result.get('intent'):
            detail += '\n\nLocal follow-up: ' + result['intent']
            if result.get('query'):
                detail += '\nSuggested search: ' + result['query']
            self.follow_up_query = result.get('query', '') if result['intent'] == 'find_app' else ''
        self._text(detail)
        self.review_button.configure(state='normal' if self.pending else 'disabled')
        if self.pending:
            if result.get('requires_popup'):
                self.approval_status.set('⚠️ High-impact action · review and click Approve & Run Now')
            else:
                self.approval_status.set('Ready to execute · expires in 2 minutes')
        else:
            self.approval_status.set('Completed · no pending desktop action.')

    def error(self, message):
        self._changed()
        self.title.set('Needs your attention')
        self._text(message)
        self.approval_status.set('Nothing new was dispatched. Edit the request and try again.')

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
                self.approval_status.set('✓ Executed. Ready for your next command.')
        except BrokerError as exc:
            if not self.closed:
                self.error(str(exc))
        finally:
            self.modal_active = False

    def cancel(self):
        self._changed()
        self.title.set('Cancelled')
        self._text('Pending proposals and any in-flight AI result were discarded.')
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

    def interpret(self, require_disclosure=False):
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

        self._record_history(text)
        disclosed_revision = self.revision

        # Only show a blocking disclosure modal if Auto-Approve is turned OFF or explicitly requested
        if require_disclosure or not self.auto_approve.get():
            cloud = cfg.kind == 'openai'
            self.modal_active = True
            try:
                approved = messagebox.askokcancel(
                    'Send this request to AI?',
                    ('CLOUD · provider charges and retention may apply.\n' if cloud else 'LOCAL MODEL · no bundled inference engine.\n')
                    + f'Provider: {cfg.base_url}\nModel: {cfg.model}\n\n'
                    'Only this request and capability instructions are sent.\n\nRequest:\n' + text,
                    parent=self.root,
                    default='ok',
                )
            finally:
                self.modal_active = False
            if not approved or self.closed:
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
        self.title.set('AI Agent interpreting request…')
        self._text('Analyzing intent and resolving targets in the background…')
        self.approval_status.set('AI working…')
        self.status.set(f'AI request in progress ({cfg.model})')

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
                        offered = self.broker.complete_interpretation(ticket, plan)
                        self.show_plan(offered)
                        # If Auto-Approve is ON and the action does not require a destructive popup, execute directly!
                        if (self.pending and self.auto_approve.get() and not self.demo
                                and not offered.get('requires_popup', False)):
                            self.confirm()
                    except BrokerError as exc:
                        self.error(str(exc))
        try:
            picker, revision, token, error = self.executable_mailbox.get_nowait()
        except queue.Empty:
            pass
        else:
            self.discovery_busy = False
            if not error and not self.closed and self.revision == revision and picker.winfo_exists():
                try:
                    offered = self.broker.select_app(token)
                    self.show_plan(offered)
                    picker.destroy()
                    if self.pending and self.auto_approve.get() and not self.demo:
                        self.confirm()
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
        self.status.set(
            'DEMO · simulation mode (no desktop effects or AI)' if self.demo else
            'Local skills & background discovery ready · AI off' if cfg.kind == 'off' else
            f'⚡ Autonomous AI active · {cfg.model} · Exploit Shield ON'
        )

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
        win.title('Discover & Launch Windows Apps · CompControl')
        win.geometry('740x560')
        win.minsize(540, 420)
        win.configure(bg=BG)
        win.transient(self.root)
        self._label(
            win,
            'Tip: You can also just type "open <App Name>" in the main bar for automatic background launch!',
            fg=ACCENT,
            font=('Segoe UI', 9, 'bold'),
            wraplength=660,
        ).pack(fill='x', padx=20, pady=(14, 4))
        query = tk.StringVar(value=getattr(self, 'follow_up_query', ''))
        tk.Entry(win, textvariable=query, bg=PANEL, fg=FG, insertbackground=FG, relief='flat', font=('Segoe UI', 11)).pack(
            fill='x', padx=20, ipady=7, pady=(4, 6)
        )
        listing = tk.Listbox(win, bg=PANEL, fg=FG, selectmode='browse', exportselection=False, relief='flat', font=('Segoe UI', 10))
        listing.pack(fill='both', expand=True, padx=20, pady=8)
        detail = tk.StringVar(value='Scanning Start menu registrations…')
        self._label(win, textvariable=detail, wraplength=660).pack(fill='x', padx=20, pady=6)
        rows, shown = [], []

        def filter_rows(*_):
            nonlocal shown
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
            detail.set(error or f'{len(rows)} apps found. Select one or double-click to launch.')

        def scan_apps():
            nonlocal rows
            if self.discovery_busy:
                return
            self._changed()
            rows = []
            filter_rows()
            self.discovery_busy = True
            scan.configure(state='disabled')
            detail.set('Reading Windows Start menu locally…')

            def work():
                try:
                    result, error = catalog.scan(), None
                except Exception:
                    result, error = [], 'Windows app discovery failed or timed out.'
                self.discovery_mailbox.put((result, error, win, render))

            threading.Thread(target=work, daemon=True).start()

        def select_app(_=None):
            indexes = listing.curselection()
            if not indexes:
                return
            try:
                token, target = shown[indexes[0]]
                if not target.packaged:
                    detail.set('Classic entry: select its trusted executable (.exe).')
                    select_exe()
                    return
                offered = self.broker.select_app(token)
                self.show_plan(offered)
                win.destroy()
                if self.pending and self.auto_approve.get() and not self.demo:
                    self.confirm()
            except ValueError as exc:
                detail.set(str(exc))

        def select_exe():
            self._changed()
            revision = self.revision
            value = filedialog.askopenfilename(
                parent=win,
                title='Select a local executable (.exe)',
                filetypes=[('Windows executable', '*.exe')],
            )
            if not value or revision != self.revision:
                return
            self.discovery_busy = True
            detail.set('Verifying selected executable…')

            def work():
                try:
                    token, error = catalog.add_executable(value), None
                except Exception:
                    token, error = None, 'Executable selection failed.'
                self.executable_mailbox.put((win, revision, token, error))

            threading.Thread(target=work, daemon=True).start()

        buttons = tk.Frame(win, bg=BG)
        buttons.pack(fill='x', padx=20, pady=12)
        scan = self._button(buttons, 'Rescan Start Menu', scan_apps)
        scan.pack(side='left')
        self._button(buttons, 'Browse .exe…', select_exe).pack(side='left', padx=8)
        choose = self._button(buttons, 'Launch Selected App ⚡', select_app, primary=True)
        choose.pack(side='right')
        choose.configure(state='disabled')
        query.trace_add('write', filter_rows)
        listing.bind('<<ListboxSelect>>', selected)
        listing.bind('<Double-Button-1>', select_app)
        # Auto-scan immediately when the window opens so the user doesn't have to click Scan first!
        win.after(50, scan_apps)

    def settings(self):
        if self.modal_active:
            return
        if self.settings_window is not None and self.settings_window.winfo_exists():
            self.settings_window.lift()
            return
        win = tk.Toplevel(self.root)
        self.settings_window = win
        win.title('AI Engine Configuration · CompControl')
        win.configure(bg=BG)
        win.geometry('640x660')
        win.minsize(560, 620)
        win.transient(self.root)
        body = tk.Frame(win, bg=BG, padx=24, pady=20)
        body.pack(fill='both', expand=True)
        self._label(body, '⚡ Autonomous AI Provider Setup', fg=FG, font=('Segoe UI', 16, 'bold')).pack(fill='x')
        self._label(
            body,
            'Connect Groq, Gemini, NVIDIA NIM, or local Ollama. Once applied, CompControl routes natural language '
            'requests automatically without repetitive confirmation popups.',
            wraplength=560,
        ).pack(fill='x', pady=(6, 12))
        cfg = self.provider.config
        label = tk.StringVar(value='Groq (cloud)' if cfg.kind == 'off' else preset_for(cfg))
        values = {key: tk.StringVar(value=getattr(cfg, key)) for key in ('base_url', 'model', 'api_key')}
        remember = tk.BooleanVar(value=CONFIG_PATH.is_file())
        picker = ttk.Combobox(body, textvariable=label, values=list(PRESETS), state='readonly')
        picker.pack(fill='x')
        hint = self._label(body, wraplength=560)
        hint.pack(fill='x', pady=(6, 0))

        def choose(_=None):
            preset = PRESETS[label.get()]
            values['base_url'].set(preset.base_url)
            values['model'].set(preset.model)
            values['api_key'].set('')
            hint.configure(text=preset.note)

        picker.bind('<<ComboboxSelected>>', choose)
        if cfg.kind == 'off':
            choose()
        else:
            hint.configure(text=PRESETS[label.get()].note)
        for key, title in [
            ('base_url', 'API base URL (filled by preset)'),
            ('model', 'Model ID (editable)'),
            ('api_key', 'API key (masked)'),
        ]:
            self._label(body, title, fg=FG).pack(fill='x', pady=(10, 4))
            field = tk.Entry(
                body,
                textvariable=values[key],
                bg=PANEL,
                fg=FG,
                insertbackground=FG,
                show='•' if key == 'api_key' else '',
                relief='flat',
            )
            field.pack(fill='x', ipady=7)
        values['base_url'].trace_add('write', lambda *_: values['api_key'].set(''))

        tk.Checkbutton(
            body,
            text='Remember AI settings on this PC (saved with private 0600 permissions)',
            variable=remember,
            bg=BG,
            fg=FG,
            selectcolor=PANEL,
            activebackground=BG,
            activeforeground=FG,
        ).pack(anchor='w', pady=(10, 4))

        info = self._label(
            body,
            'Keys are never included in prompts or activity logs.',
            wraplength=560,
        )
        info.pack(fill='x', pady=8)
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
                new_cfg = read_config()
                self.provider = TextProvider(new_cfg)
                if remember.get():
                    save_provider_config(new_cfg)
                elif CONFIG_PATH.is_file():
                    CONFIG_PATH.unlink()
            except ProviderError as exc:
                info.configure(text=str(exc))
                return
            self._changed()
            self._provider_status()
            self.title.set('AI Engine Active')
            self._text(
                f'Connected to {new_cfg.model}.\n'
                'Type any natural command and press Enter — CompControl will interpret and execute it seamlessly.'
            )
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
            info.configure(
                text=result if revision == sent_revision else
                'Settings changed during the test. Test the new settings before applying.'
            )

        def test():
            nonlocal testing, timer
            if self.demo or self.ai_busy or testing:
                info.configure(text='Testing is disabled in demo mode or while another API request is running.')
                return
            try:
                config = read_config()
                if config.kind == 'off':
                    raise ProviderError('Choose a cloud or local provider to test AI.')
            except ProviderError as exc:
                info.configure(text=str(exc))
                return
            sent_revision = revision
            self._changed()
            testing = True
            self.ai_busy = True
            self._provider_status()
            test_button.configure(state='normal' if not testing else 'disabled')
            info.configure(text='Testing API authentication and structured output…')

            def worker():
                try:
                    plan = TextProvider(config).propose('open calculator')
                    from .models import Action
                    result = (
                        '✓ Test passed: provider returned the expected Calculator proposal. Click Apply!'
                        if plan.actions == (Action('app', 'calculator'),)
                        else 'Provider responded, but did not return the expected action. Try another text model.'
                    )
                except ProviderError as exc:
                    result = str(exc)
                except Exception:
                    result = 'API test failed. Check the endpoint, model, and API key.'
                replies.put((sent_revision, result))

            threading.Thread(target=worker, daemon=True).start()
            timer = win.after(100, poll_test)

        def close():
            if testing:
                info.configure(text='Wait for the API test to finish before closing.')
                return
            if timer is not None:
                win.after_cancel(timer)
            values['api_key'].set('')
            win.destroy()

        win.protocol('WM_DELETE_WINDOW', close)
        buttons = tk.Frame(body, bg=BG)
        buttons.pack(fill='x', pady=(8, 0))
        test_button = self._button(buttons, 'Test AI Connection', test)
        test_button.pack(side='left')
        self._button(buttons, 'Apply & Activate ⚡', apply, primary=True).pack(side='right')

    def activity(self):
        win = tk.Toplevel(self.root)
        win.title('Session Activity & Telemetry · CompControl')
        win.geometry('540x440')
        win.configure(bg=BG)
        self._label(win, 'Session Activity & System Telemetry (zero prompts/secrets logged)', fg=FG, wraplength=480).pack(
            padx=20, pady=(16, 8)
        )
        text = tk.Text(win, bg=PANEL, fg=FG, wrap='word', relief='flat', height=14, font=('Consolas', 10), padx=12, pady=10)
        text.pack(fill='both', expand=True, padx=20)
        events = self.broker.state()['activity']
        telemetry = collect_system_telemetry('system_info')
        log_body = '\n'.join(f"{e['time']}   {e['title']} — {e['status']}" for e in events) or 'No session activity yet.'
        text.insert('1.0', f'=== SYSTEM TELEMETRY ===\n{telemetry}\n\n=== SESSION ACTIVITY ===\n{log_body}')
        text.configure(state='disabled')

        def clear():
            self.broker.clear()
            self.cancel()
            win.destroy()

        self._button(win, 'Clear Activity & Pending Work', clear).pack(pady=16)

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
