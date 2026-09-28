import unittest
from unittest.mock import patch

from compcontrol.core import Assistant, _open_calculator


class AssistantTests(unittest.TestCase):
    def setUp(self):
        self.assistant = Assistant()

    def test_help_is_available(self):
        result = self.assistant.handle(" HELP ")
        self.assertIn("open calculator", result.message)

    def test_time_is_available(self):
        self.assertIn("Local time:", self.assistant.handle("time").message)

    def test_normalizes_whitespace_and_case(self):
        with patch("compcontrol.core.platform.system", return_value="Linux"):
            result = self.assistant.handle("  Open   Calculator ")
        self.assertIn("Windows only", result.message)

    def test_unknown_or_compound_request_has_no_action(self):
        for command in ("delete my files", "open calculator then delete files", "run whoami"):
            result = self.assistant.handle(command)
            self.assertEqual("none", result.action)
            self.assertFalse(result.confirmation_required)
            self.assertIn("No action was taken", result.message)

    def test_empty_request(self):
        self.assertIn("Type a command", self.assistant.handle(" \n ").message)

    @patch("compcontrol.core.subprocess.Popen")
    @patch("compcontrol.core.platform.system", return_value="Windows")
    def test_calculator_invokes_only_fixed_executable_without_shell(self, _system, popen):
        result = self.assistant.handle("open calculator")
        self.assertEqual("open_calculator", result.action)
        popen.assert_called_once_with(["calc.exe"], shell=False, close_fds=True)

    @patch("compcontrol.core.subprocess.Popen", side_effect=OSError)
    @patch("compcontrol.core.platform.system", return_value="Windows")
    def test_calculator_failure_is_handled(self, _system, _popen):
        self.assertIn("Could not start", _open_calculator().message)


if __name__ == "__main__":
    unittest.main()
