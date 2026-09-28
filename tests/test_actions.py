import unittest
from pathlib import Path
from unittest.mock import patch
from compcontrol.actions import WindowsExecutor, ActionError
from compcontrol.models import Action


class ActionsTests(unittest.TestCase):
    def execute(self,action,consent=lambda *_:True,valid=lambda:True):
        return WindowsExecutor(consent).execute(action,lambda f:f(),valid)
    @patch('compcontrol.actions.platform.system',return_value='Windows')
    @patch('compcontrol.actions.app_path',return_value=Path('/trusted/chrome.exe'))
    @patch('compcontrol.actions.subprocess.Popen')
    def test_browser_argv_never_shell(self,popen,path,system):
        result=self.execute(Action('search','youtube','hello & --evil', 'chrome'))
        args,kwargs=popen.call_args
        self.assertEqual(args[0],[str(Path('/trusted/chrome.exe')),'https://www.youtube.com/results?search_query=hello+%26+--evil'])
        self.assertFalse(kwargs['shell'])
        self.assertEqual(result['status'],'executed')
    @patch('compcontrol.actions.platform.system',return_value='Windows')
    @patch('compcontrol.actions.app_path',return_value=Path('/trusted/calc.exe'))
    @patch('compcontrol.actions.subprocess.Popen')
    def test_decline_does_nothing(self,popen,path,system):
        result=self.execute(Action('app','calculator'),lambda *_:False)
        self.assertEqual(result['status'],'cancelled');popen.assert_not_called()
    @patch('compcontrol.actions.platform.system',return_value='Linux')
    def test_platform_fails_closed(self,system):
        with self.assertRaises(ActionError):self.execute(Action('app','calculator'))
