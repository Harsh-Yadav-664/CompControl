import unittest
from unittest.mock import patch
from urllib.parse import urlsplit, parse_qs, unquote
from compcontrol.core import Assistant
from compcontrol.models import Action
from compcontrol.actions import validate, destination, ActionError
from compcontrol.planner import plan_request, calculate


class PlannerTests(unittest.TestCase):
    def action(self, text):
        plan = plan_request(text)
        self.assertEqual(len(plan.actions), 1, plan)
        return plan.actions[0]

    def test_handle_has_no_side_effect(self):
        with patch('subprocess.Popen') as popen:
            result = Assistant().handle('open calculator')
            self.assertTrue(result.confirmation_required)
            popen.assert_not_called()

    def test_help_and_time_are_offline(self):
        for text in ('help', 'time', 'what time is it'):
            self.assertFalse(plan_request(text).actions)

    def test_persona_politeness_and_normalization(self):
        action = self.action('Hey Jarvis, please Open   Calculator!')
        self.assertEqual(action, Action('app', 'calculator'))

    def test_unknown_and_compound_are_not_executed(self):
        for text in ('delete my files','open calculator then delete files','run whoami',
                     'open brave and run powershell','open notepad & calc', 'open C:\\evil.exe'):
            with self.subTest(text=text):
                self.assertFalse(plan_request(text).actions)

    def test_exact_browser_is_preserved(self):
        self.assertEqual(self.action('open Brave'), Action('app', 'brave'))
        a = self.action('open Brave and search for Sidemen videos on YouTube')
        self.assertEqual(a, Action('search', 'youtube', 'Sidemen videos', 'brave'))

    def test_user_examples(self):
        cases = {
            'open Spotify and play sad Hindi songs': ('search', 'spotify', 'sad Hindi songs'),
            'open Spotify and play my liked playlist': ('liked', 'spotify', ''),
            'open Chrome and search for Sidemen videos on YouTube': ('search','youtube','Sidemen videos'),
            'search YouTube for Sidemen videos': ('search','youtube','Sidemen videos'),
            'YouTube search for Sidemen videos': ('search','youtube','Sidemen videos'),
            'play sad Hindi songs on Spotify': ('search','spotify','sad Hindi songs'),
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                a = self.action(text)
                self.assertEqual((a.kind,a.target,a.query),expected)

    def test_empty_input_search(self):
        for text in ('', ' ', 'search', 'search for', 'google', 'search Spotify for'):
            self.assertFalse(plan_request(text).actions)

    def test_query_case_unicode_and_encoding(self):
        for site in ('youtube','google','maps','spotify'):
            a = self.action(f'search {site} for हिन्दी Music & --flag="x" # ?')
            url = destination(a)
            self.assertTrue(url.startswith('https://'))
            self.assertNotIn(' ',url)
            self.assertFalse(urlsplit(url).fragment)
            self.assertIn('Music',unquote(url))

    def test_no_silent_truncation_or_control_chars(self):
        for text in ('x'*1001, 'search for '+'x'*301, 'search for evil\x00', 'open\ncalculator', 'search for \u202eexe'):
            with self.assertRaises(ValueError):
                plan_request(text)

    def test_arithmetic_bounded_no_eval(self):
        self.assertEqual(calculate('(2400 * .18) + 2400'), '2832')
        self.assertEqual(calculate('-10 // 3'), '-4')
        for text in ('__import__("os")', '2**999999', '1/0', '1e999', 'True', '9'*101, '(1).__class__'):
            with self.assertRaises(ValueError):
                calculate(text)

    def test_media_toggle_not_false_state(self):
        for text in ('pause music', 'resume music'):
            self.assertFalse(plan_request(text).actions)
        self.assertEqual(self.action('toggle playback').target,'play_pause')

    def test_allowlist_rejects_forged_actions(self):
        for action in (Action('shell','calc'), Action('app','cmd'), Action('site','https://evil'),
                       Action('search','youtube','ok','evil'), Action('app','notepad','--help'),
                       Action('search','spotify','x\n'), Action('app','calculator',browser='chrome')):
            with self.assertRaises(ActionError):
                validate(action)

    def test_invalid_browser_preference(self):
        with self.assertRaises(ValueError):
            plan_request('help','malware')


if __name__ == '__main__':
    unittest.main()
