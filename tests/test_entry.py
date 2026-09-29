import sys
import types
import unittest
from unittest.mock import Mock, patch

from compcontrol.__main__ import main


class EntryTests(unittest.TestCase):
    def test_default_is_native_not_web(self):
        native = types.ModuleType('compcontrol.desktop')
        native.run_desktop = Mock()
        with patch.dict(sys.modules, {'compcontrol.desktop': native}), \
                patch.object(sys, 'argv', ['compcontrol', '--demo']), \
                patch('compcontrol.server.serve') as serve:
            self.assertEqual(main(), 0)
        native.run_desktop.assert_called_once_with(True)
        serve.assert_not_called()

    def test_widget_stays_native_and_is_forwarded(self):
        native = types.ModuleType('compcontrol.desktop')
        native.run_desktop = Mock()
        with patch.dict(sys.modules, {'compcontrol.desktop': native}), \
                patch.object(sys, 'argv', ['compcontrol', '--demo', '--widget']):
            self.assertEqual(main(), 0)
        native.run_desktop.assert_called_once_with(True, widget=True)
        with patch.object(sys, 'argv', ['compcontrol', '--web', '--widget']), \
                patch('sys.stderr'), self.assertRaises(SystemExit):
            main()

    def test_web_requires_explicit_flag(self):
        with patch.object(sys, 'argv', ['compcontrol', '--web', '--demo', '--no-open']), \
                patch('compcontrol.server.serve') as serve:
            self.assertEqual(main(), 0)
        serve.assert_called_once_with('127.0.0.1', 8765, True, False)

    def test_real_actions_require_windows(self):
        with patch.object(sys, 'argv', ['compcontrol']), \
                patch('compcontrol.__main__.platform.system', return_value='Linux'), \
                patch('sys.stderr'), self.assertRaises(SystemExit) as error:
            main()
        self.assertEqual(error.exception.code, 2)

    def test_modes_are_exclusive(self):
        with patch.object(sys, 'argv', ['compcontrol', '--cli', '--web']), \
                patch('sys.stderr'), self.assertRaises(SystemExit):
            main()
