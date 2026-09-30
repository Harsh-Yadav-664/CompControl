"""Native UI integration tests; run on Windows or Linux with Tk + Xvfb."""
import time
import unittest
from unittest.mock import Mock, patch

try:
    import tkinter as tk
except ImportError:
    tk = None
else:
    from compcontrol.desktop import DesktopApp

from compcontrol.broker import Broker, DemoExecutor
from compcontrol.models import Plan, Action
from compcontrol.providers import ProviderConfig


@unittest.skipIf(tk is None, 'Tcl/Tk not installed')
class DesktopTests(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError:
            self.skipTest('No desktop display (use xvfb-run)')
        self.errors = []
        self.root.report_callback_exception = lambda *args: self.errors.append(args)
        self.app = DesktopApp(self.root, demo=True, hotkey=False)
        self.root.update()

    def tearDown(self):
        self.app.close()
        self.assertFalse(self.errors, self.errors)

    def test_plan_edit_and_simulation(self):
        self.app.request.set('open a youtube tab and find Sidemen videos')
        self.app.plan()
        old = self.app.pending
        self.assertTrue(old)
        self.assertIn('Sidemen', self.app.output.get('1.0', 'end'))
        self.app.request.set('open notepad')
        self.assertIsNone(self.app.pending)
        self.assertIsNone(self.app.broker.state()['pending_id'])
        self.app.plan()
        self.app.confirm()
        self.assertEqual(self.app.title.get(), 'Simulated')

    def test_widget_settings_pause_activity(self):
        self.app.compact.set(True)
        self.app._compact()
        self.root.update()
        self.assertFalse(self.app.shortcuts.winfo_ismapped())
        self.app.compact.set(False)
        self.app._compact()
        self.root.update()
        self.assertTrue(self.app.shortcuts.winfo_ismapped())
        self.app.settings()
        self.app.activity()
        self.app.pause()
        self.assertTrue(self.app.broker.state()['paused'])
        self.app.shortcut('open calculator')
        self.assertIsNone(self.app.pending)

    def test_cloud_presets_fill_fields_and_clear_other_provider_key(self):
        self.app.settings()
        win = self.app.settings_window
        self.root.update()

        def descendants(widget):
            for child in widget.winfo_children():
                yield child
                yield from descendants(child)

        widgets = list(descendants(win))
        picker = next(w for w in widgets if w.winfo_class() == 'TCombobox')
        fields = [w for w in widgets if w.winfo_class() == 'Entry']
        self.assertEqual(picker.get(), 'Groq (cloud)')
        self.assertEqual(fields[0].get(), 'https://api.groq.com/openai/v1')
        fields[2].insert(0, 'do-not-forward')
        picker.set('Gemini (cloud)')
        picker.event_generate('<<ComboboxSelected>>')
        self.root.update()
        self.assertEqual(fields[2].get(), '')
        self.assertIn('generativelanguage.googleapis.com', fields[0].get())
        fields[2].insert(0, 'second-key')
        fields[0].insert('end', '/changed')
        self.assertEqual(fields[2].get(), '')

    def test_demo_cannot_enable_provider_from_environment(self):
        self.assertEqual(self.app.provider.config.kind, 'off')
        self.app.interpret()
        self.assertIsNone(self.app.pending)

    def test_ai_worker_auto_approves_by_default_and_manual_when_toggled(self):
        self.app.demo = False
        self.app.broker = Broker(DemoExecutor())
        provider = Mock()
        provider.config = ProviderConfig('ollama', 'http://127.0.0.1:11434', 'fake-model')
        provider.propose.return_value = Plan('Open Calculator', 'Local summary', (Action('app', 'calculator'),))
        self.app.provider = provider

        # 1. With Auto-Approve ON (default), interpret() executes directly without intermediate click
        self.app.auto_approve.set(True)
        self.app.request.set('could you bring up my calculator please')
        self.app.interpret()
        deadline = time.monotonic() + 3
        while self.app.ai_busy and time.monotonic() < deadline:
            self.root.update()
            time.sleep(.01)
        self.assertFalse(self.app.ai_busy)
        self.assertIsNone(self.app.pending)
        self.assertEqual(self.app.title.get(), 'Simulated')

        # 2. With Auto-Approve OFF, proposal waits for confirmation and edits discard it
        self.app.auto_approve.set(False)
        self.app.request.set('open calculator manually')
        with patch('compcontrol.desktop.messagebox.askokcancel', return_value=True):
            self.app.interpret()
        deadline = time.monotonic() + 3
        while self.app.ai_busy and time.monotonic() < deadline:
            self.root.update()
            time.sleep(.01)
        self.assertFalse(self.app.ai_busy)
        self.assertTrue(self.app.pending)
        self.assertTrue(self.app.title.get().startswith('AI proposal'))
        self.app.request.set('a different request')
        self.assertIsNone(self.app.pending)
        self.app.ai_busy = True
        self.app.mailbox.put((self.app.revision - 1, 'stale', provider.propose.return_value, None))
        self.root.after_cancel(self.app.timer)
        self.app._tick()
        self.assertIsNone(self.app.pending)

    def test_declined_disclosure_never_calls_provider_when_auto_approve_off(self):
        self.app.demo = False
        self.app.auto_approve.set(False)
        provider = Mock()
        provider.config = ProviderConfig('ollama', 'http://127.0.0.1:11434', 'fake-model')
        self.app.provider = provider
        self.app.request.set('an unusual request')
        with patch('compcontrol.desktop.messagebox.askokcancel', return_value=False):
            self.app.interpret()
        provider.propose.assert_not_called()

    def test_native_dialog_revocation_with_parent(self):
        from compcontrol.consent import native_confirm
        self.assertFalse(native_confirm('Test approval', 'Not an actual action', lambda: False, parent=self.root))
        self.root.update()


if __name__ == '__main__':
    unittest.main()
