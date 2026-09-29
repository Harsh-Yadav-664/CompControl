import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
import urllib.error
from unittest.mock import Mock

from compcontrol.actions import destination, WindowsExecutor
from compcontrol.models import Action
from compcontrol.planner import plan_request
from compcontrol.provider_presets import PRESETS, config_from_fields, preset_for
from compcontrol.providers import ProviderConfig, ProviderError, TextProvider
from unittest.mock import patch


class CloudSetupTests(unittest.TestCase):
    def test_presets_make_cloud_requests_not_local_inference(self):
        for label in ('Groq (cloud)', 'Gemini (cloud)', 'NVIDIA NIM (cloud)'):
            with self.subTest(label=label):
                p = PRESETS[label]
                cfg = config_from_fields(label, p.base_url + '/', p.model, 'test-secret')
                self.assertTrue(cfg.public()['cloud'])
                self.assertEqual(preset_for(cfg), label)
                transport = Mock()
                proposal = {'action': {'kind': 'app', 'target': 'calculator', 'query': ''}}
                transport.open.return_value = io.BytesIO(json.dumps({'choices': [
                    {'message': {'content': json.dumps(proposal)}, 'finish_reason': 'stop'}]}).encode())
                result = TextProvider(cfg, transport).propose('open calculator')
                self.assertEqual(result.actions, (Action('app', 'calculator'),))
                request = transport.open.call_args.args[0]
                self.assertEqual(request.full_url, p.base_url + '/chat/completions')
                self.assertEqual(request.headers['Authorization'], 'Bearer test-secret')
                self.assertNotIn('test-secret', request.data.decode())
                payload = json.loads(request.data)
                self.assertNotIn('tools', payload)
                if label.startswith('Groq'):
                    self.assertEqual(payload['response_format'], {'type': 'json_object'})
                    self.assertEqual(payload['reasoning_effort'], 'low')
                    self.assertEqual(payload['max_tokens'], 2048)
                if label.startswith('Gemini'):
                    self.assertEqual(payload['extra_body']['google']['thinking_config']['thinking_budget'], 0)
                if label.startswith('NVIDIA'):
                    self.assertNotIn('extra_body', payload)
                    self.assertNotIn('reasoning_effort', payload)

    def test_custom_api_does_not_receive_vendor_options(self):
        transport = Mock()
        transport.open.return_value = io.BytesIO(b'{"choices":[{"message":{"content":"hello"}}]}')
        TextProvider(ProviderConfig('openai', 'https://example.com/v1/', 'custom', 'secret'), transport).answer('hi')
        request = transport.open.call_args.args[0]
        self.assertEqual(request.full_url, 'https://example.com/v1/chat/completions')
        self.assertNotIn('reasoning_effort', json.loads(request.data))

    def test_rate_limit_and_auth_errors_do_not_retry_or_leak_key(self):
        for code, hint in [(401, 'key'), (403, 'access'), (404, 'not found'), (429, 'quota')]:
            transport = Mock()
            transport.open.side_effect = urllib.error.HTTPError('https://example.com', code, 'PRIVATE-SECRET', {}, None)
            provider = TextProvider(ProviderConfig('openai', 'https://example.com/v1', 'm', 'PRIVATE-SECRET'), transport)
            with self.assertRaises(ProviderError) as error:
                provider.answer('hi')
            self.assertIn(hint, str(error.exception))
            self.assertNotIn('PRIVATE-SECRET', str(error.exception))
            transport.open.assert_called_once()

    def test_length_limited_even_if_valid_json_is_not_accepted(self):
        transport = Mock()
        proposal = json.dumps({'action': {'kind': 'app', 'target': 'calculator', 'query': ''}})
        transport.open.return_value = io.BytesIO(json.dumps({'choices': [{'message': {'content': proposal},
                                                                         'finish_reason': 'length'}]}).encode())
        with self.assertRaisesRegex(ProviderError, 'output limit'):
            TextProvider(ProviderConfig('openai', 'https://example.com/v1', 'm'), transport).propose('open calculator')

    def test_off_drops_fields_and_unsafe_url_rejected(self):
        self.assertEqual(config_from_fields('Off (local skills only)', 'https://example.com', 'm', 'secret'), ProviderConfig())
        with self.assertRaises(ProviderError):
            config_from_fields('Groq (cloud)', 'http://example.com', 'm', 'secret')

    def test_screenshot_wording_dispatches_encoded_url_on_windows(self):
        plan = plan_request('open yt and search for mr whose the boss')
        self.assertEqual(plan.actions, (Action('search', 'youtube', 'mr whose the boss'),))
        expected = 'https://www.youtube.com/results?search_query=mr+whose+the+boss'
        self.assertEqual(destination(plan.actions[0]), expected)
        with patch('compcontrol.actions.platform.system', return_value='Windows'), \
                patch('compcontrol.actions.os.startfile', create=True) as launch:
            executor = WindowsExecutor(consent=lambda *_: True)
            executor.execute(plan.actions[0], lambda dispatch: dispatch(), lambda: True)
            launch.assert_called_once_with(expected)
        self.assertEqual(plan_request('open yt').actions, (Action('site', 'youtube'),))


class SourceLauncherTests(unittest.TestCase):
    def test_command_handles_space_in_path_and_widget(self):
        path = Path(__file__).resolve().parents[1] / 'scripts' / 'launch-windows.py'
        spec = importlib.util.spec_from_file_location('launcher', path)
        launcher = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(launcher)
        with tempfile.TemporaryDirectory(prefix='CompControl with spaces ') as temp:
            root = Path(temp)
            (root / 'pythonw.exe').touch()
            result = launcher.command(root / 'python.exe', root, widget=True)
            self.assertEqual(result, [str(root / 'pythonw.exe'), str(root / 'scripts/start-windows.pyw'), '--widget'])
        with self.assertRaises(ValueError):
            launcher.command(Path('/missing/python.exe'), Path('/missing'))
