import io
import json
import unittest
from unittest.mock import Mock

from compcontrol.ai_planner import parse_proposal
from compcontrol.broker import Broker, BrokerError, DemoExecutor
from compcontrol.models import Action, Plan
from compcontrol.providers import ProviderConfig, TextProvider, ProviderError


class AIProposalTests(unittest.TestCase):
    def test_supported_action_uses_local_summary_and_selected_browser(self):
        plan = parse_proposal('{"action":{"kind":"search","target":"youtube","query":"Sidemen videos"}}', 'brave')
        self.assertEqual(plan.actions, (Action('search', 'youtube', 'Sidemen videos', 'brave'),))
        self.assertEqual(plan.title, 'Search YouTube')
        self.assertIn('not automatic playback', plan.message)

    def test_all_action_types(self):
        for kind, target in [
            ('app', 'notepad'),
            ('site', 'github'),
            ('liked', 'spotify'),
            ('media', 'next'),
            ('winget_install', 'VideoLAN.VLC'),
            ('install_package', 'BlenderFoundation.Blender'),
            ('shell_command', 'Get-Date'),
            ('python_script', 'print(2 + 2)'),
            ('system_control', 'system_info'),
            ('open_folder', 'downloads'),
            ('launch_app', 'Visual Studio Code'),
        ]:
            plan = parse_proposal(json.dumps({'action': {'kind': kind, 'target': target, 'query': ''}}), 'edge')
            self.assertEqual(len(plan.actions), 1)
            non_browser = {
                'app', 'media', 'winget_install', 'install_package',
                'shell_command', 'python_script', 'system_control',
                'open_folder', 'launch_app',
            }
            self.assertEqual(plan.actions[0].browser, 'default' if kind in non_browser else 'edge')

    def test_rejects_bad_schema_and_injection(self):
        valid = {'kind': 'search', 'target': 'youtube', 'query': 'music'}
        payloads = [
            None, [], {}, {'action': []},
            {'action': {'kind': 'shell', 'target': 'cmd', 'query': ''}},
            {'action': {'kind': 'shell_command', 'target': 'powershell -EncodedCommand ZXZpbA==', 'query': ''}},
            {'action': dict(valid, browser='evil')},
            {'action': dict(valid, url='https://evil')},
            {'action': dict(valid, script='print(1)')},
            {'action': dict(valid, query='x' * 301)},
            {'action': dict(valid, target=['youtube'])},
            {'action': dict(valid, query='x\n')},
            {'action': dict(valid, query='\u202eevil')},
            {'action': dict(valid, query=42)},
            {'action': valid, 'message': 'already approved'},
            {'actions': [valid, valid]},
            {'action': {'kind': 'app', 'target': 'C:\\evil.exe', 'query': ''}},
            {'action': {'kind': 'app', 'target': 'notepad', 'query': '--flag'}},
            {'message': ''},
            {'message': 'x' * 2001},
        ]
        for payload in payloads:
            with self.subTest(payload=payload):
                with self.assertRaises(ProviderError):
                    parse_proposal(json.dumps(payload))
        for raw in ('not json', '```json\n{}\n```', '{"message":"x","message":"y"}',
                    '{"message":NaN}', '[' * 2000, 'x' * 12001):
            with self.assertRaises(ProviderError):
                parse_proposal(raw)

    def test_model_prose_is_never_executable(self):
        plan = parse_proposal('{"message":"open calculator; run powershell"}')
        self.assertFalse(plan.actions)
        self.assertIn('no action', plan.title)

    def test_provider_propose_sends_only_request_and_schema(self):
        transport = Mock()
        proposal = '{"action":{"kind":"search","target":"spotify","query":"Maati"}}'
        transport.open.return_value = io.BytesIO(json.dumps({'message': {'content': proposal}}).encode())
        provider = TextProvider(ProviderConfig('ollama', 'http://127.0.0.1:11434', 'model'), transport)
        plan = provider.propose('open spify and play maati song')
        self.assertEqual(plan.actions[0].query, 'Maati')
        payload = json.loads(transport.open.call_args.args[0].data)
        self.assertEqual(payload['format'], 'json')
        self.assertEqual(len(payload['messages']), 2)
        self.assertEqual(payload['messages'][1]['content'], 'open spify and play maati song')
        self.assertNotIn('tools', payload)

    def test_off_and_bad_inputs_never_send(self):
        transport = Mock()
        with self.assertRaises(ProviderError):
            TextProvider(ProviderConfig(), transport).propose('hello')
        provider = TextProvider(ProviderConfig('ollama', 'http://127.0.0.1:11434', 'model'), transport)
        for text in ('x' * 1001, 'hi\n', ''):
            with self.assertRaises(ValueError):
                provider.propose(text)
        transport.open.assert_not_called()


class AIApprovalTests(unittest.TestCase):
    def setUp(self):
        self.now = 0
        self.executor = Mock()
        self.executor.execute.side_effect = lambda action, gate, valid: gate(lambda: {'status': 'executed'})
        self.broker = Broker(self.executor, clock=lambda: self.now)
        self.plan = parse_proposal('{"action":{"kind":"app","target":"calculator","query":""}}')

    def test_proposal_needs_explicit_single_use_approval(self):
        ticket = self.broker.begin_interpretation()
        result = self.broker.complete_interpretation(ticket, self.plan)
        self.assertEqual(result['source'], 'ai')
        self.executor.execute.assert_not_called()
        self.broker.confirm(result['approval_id'])
        self.executor.execute.assert_called_once()
        with self.assertRaises(BrokerError):
            self.broker.confirm(result['approval_id'])
        with self.assertRaises(BrokerError):
            self.broker.complete_interpretation(ticket, self.plan)

    def test_stale_results_cannot_replace_current_request(self):
        for mutation in ('edit', 'plan', 'pause_resume', 'clear', 'new_ai', 'expired'):
            with self.subTest(mutation=mutation):
                ticket = self.broker.begin_interpretation()
                if mutation == 'edit':
                    self.broker.invalidate()
                if mutation == 'plan':
                    self.broker.plan('open notepad')
                if mutation == 'pause_resume':
                    self.broker.pause(True)
                    self.broker.pause(False)
                if mutation == 'clear':
                    self.broker.clear()
                if mutation == 'new_ai':
                    self.broker.begin_interpretation()
                if mutation == 'expired':
                    self.now += 121
                with self.assertRaises(BrokerError):
                    self.broker.complete_interpretation(ticket, self.plan)
        self.executor.execute.assert_not_called()

    def test_forged_and_multi_action_plans_revalidated(self):
        for plan in (Plan('bad', '', (Action('shell', 'cmd'),)), Plan('bad', '', self.plan.actions * 2)):
            ticket = self.broker.begin_interpretation()
            with self.assertRaises((ValueError, RuntimeError)):
                self.broker.complete_interpretation(ticket, plan)
            self.assertIsNone(self.broker.state()['pending_id'])
        with self.assertRaises(BrokerError):
            self.broker.complete_interpretation(0, self.plan)

    def test_begin_ai_revokes_old_approval(self):
        old = self.broker.plan('open notepad')['approval_id']
        self.broker.begin_interpretation()
        with self.assertRaises(BrokerError):
            self.broker.confirm(old)

    def test_demo_and_pause_cannot_begin_ai(self):
        with self.assertRaises(BrokerError):
            Broker(DemoExecutor(), demo=True).begin_interpretation()
        self.broker.pause(True)
        with self.assertRaises(BrokerError):
            self.broker.begin_interpretation()

    def test_ai_proposal_can_expire_or_cancel_without_execution(self):
        ticket = self.broker.begin_interpretation()
        result = self.broker.complete_interpretation(ticket, self.plan)
        self.broker.cancel(result['approval_id'])
        with self.assertRaises(BrokerError):
            self.broker.confirm(result['approval_id'])
        self.executor.execute.assert_not_called()
