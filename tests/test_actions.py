import unittest
from pathlib import Path
from unittest.mock import patch, Mock
from compcontrol.actions import WindowsExecutor, ActionError
from compcontrol.consent import native_confirm, classify_risk, requires_native_popup
from compcontrol.models import Action


class ActionsTests(unittest.TestCase):
    def execute(self, action, consent=lambda *_: True, valid=lambda: True):
        return WindowsExecutor(consent).execute(action, lambda f: f(), valid)

    @patch('compcontrol.actions.platform.system', return_value='Windows')
    @patch('compcontrol.actions.app_path', return_value=Path('/trusted/chrome.exe'))
    @patch('compcontrol.actions.subprocess.Popen')
    def test_browser_argv_never_shell(self, popen, path, system):
        result = self.execute(Action('search', 'youtube', 'hello & --evil', 'chrome'))
        args, kwargs = popen.call_args
        self.assertEqual(args[0], [str(Path('/trusted/chrome.exe')), 'https://www.youtube.com/results?search_query=hello+%26+--evil'])
        self.assertFalse(kwargs['shell'])
        self.assertEqual(result['status'], 'executed')

    @patch('compcontrol.actions.platform.system', return_value='Windows')
    @patch('compcontrol.actions.app_path', return_value=Path('/trusted/calc.exe'))
    @patch('compcontrol.actions.subprocess.Popen')
    def test_decline_does_nothing(self, popen, path, system):
        result = self.execute(Action('app', 'calculator'), lambda *_: False)
        self.assertEqual(result['status'], 'cancelled')
        popen.assert_not_called()

    @patch('compcontrol.actions.platform.system', return_value='Linux')
    def test_platform_fails_closed(self, system):
        with self.assertRaises(ActionError):
            self.execute(Action('app', 'calculator'))

    @patch('compcontrol.actions.platform.system', return_value='Windows')
    @patch('compcontrol.actions.winget_path', return_value='/trusted/winget.exe')
    @patch('compcontrol.actions.subprocess.Popen')
    def test_winget_install_dispatches_natively(self, popen, *_):
        result = self.execute(Action('winget_install', 'VideoLAN.VLC', 'VLC'))
        self.assertEqual(result['status'], 'executed')
        args, kwargs = popen.call_args
        self.assertEqual(
            args[0],
            ['/trusted/winget.exe', 'install', '--id', 'VideoLAN.VLC', '-e',
             '--accept-source-agreements', '--accept-package-agreements', '--disable-interactivity'],
        )
        self.assertFalse(kwargs['shell'])

    @patch('compcontrol.actions.platform.system', return_value='Windows')
    @patch('compcontrol.actions.app_path', return_value=Path('/trusted/Code.exe'))
    @patch('compcontrol.actions.subprocess.Popen')
    def test_launch_app_dispatches_resolved_target(self, popen, *_):
        result = self.execute(Action('launch_app', 'vscode', 'Visual Studio Code'))
        self.assertEqual(result['status'], 'executed')
        popen.assert_called_once_with(['/trusted/Code.exe'], shell=False, close_fds=True)

    def test_safe_actions_bypass_native_confirm_popup(self):
        # Safe tasks (app, liked, search, winget_install, etc.) return True immediately without opening Tk
        self.assertTrue(native_confirm('CompControl', 'Request: liked\n\nspotify:collection:tracks', lambda: True))
        self.assertTrue(native_confirm('CompControl', 'Request: app\n\nExecutable: calc.exe', lambda: True))
        self.assertTrue(native_confirm('CompControl', 'Request: winget_install\n\nwinget install VideoLAN.VLC', lambda: True))
        self.assertFalse(requires_native_popup(Action('liked', 'spotify')))
        self.assertFalse(requires_native_popup(Action('winget_install', 'VideoLAN.VLC')))
        self.assertTrue(requires_native_popup(Action('shell_command', 'Remove-Item -Recurse C:\\temp')))
        self.assertEqual(classify_risk(Action('shell_command', 'powershell -EncodedCommand ZXZpbA==')), 'blocked')
