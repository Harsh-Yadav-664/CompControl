import io
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from compcontrol.actions import ActionError, WindowsExecutor, validate_url
from compcontrol.ai_planner import parse_proposal
from compcontrol.broker import Broker, BrokerError
from compcontrol.executable_target import select_executable
from compcontrol.file_workspace import snapshot, preview_replace, export_patch, PatchCatalog, WorkspaceError
from compcontrol.installed_apps import AppCatalog, InstalledApp, DiscoveryError, discover, parse_inventory
from compcontrol.models import Action, Plan
from compcontrol.planner import plan_request
from compcontrol.providers import TextProvider, ProviderConfig, ProviderError


class IntentTests(unittest.TestCase):
    def test_unknown_app_requests_discovery_not_permission(self):
        plan = plan_request('open Visual Studio Code')
        self.assertEqual(plan.intent, 'find_app')
        self.assertEqual(plan.query, 'Visual Studio Code')
        self.assertFalse(plan.actions)
        ai = parse_proposal('{"intent":"find_app","query":"Blender"}')
        self.assertEqual(ai.intent, 'find_app')
        self.assertFalse(ai.actions)

    def test_install_and_download_find_only_web_results(self):
        for text in ('install Blender', 'download the VLC for Windows',
                     'download and install Blender', 'winget install VLC'):
            plan = plan_request(text)
            self.assertEqual((plan.actions[0].kind, plan.actions[0].target), ('search', 'google'))
            self.assertIn('official download Windows', plan.actions[0].query)
            self.assertIn('has not downloaded', plan.message)
        link = plan_request('download from https://example.org/setup.exe')
        self.assertEqual(link.actions[0].kind, 'navigate')
        self.assertEqual(link.actions[0].target, 'https://example.org/setup.exe')

    def test_files_and_research_are_honest_handoffs(self):
        self.assertFalse(plan_request('project files').actions)
        research = plan_request('ask ChatGPT to do deep research on battery recycling')
        self.assertEqual(research.actions, (Action('site', 'chatgpt'),))
        self.assertIn('No text is submitted', research.message)
        self.assertIn('battery recycling', research.message)

    def test_spotify_uses_native_uri_unless_browser_explicitly_selected(self):
        from compcontrol.actions import destination
        native = plan_request('open Spotify and play Maati')
        self.assertEqual(destination(native.actions[0]), 'spotify:search:Maati')
        browser = plan_request('open Spotify and play Maati', 'edge')
        self.assertEqual(destination(browser.actions[0]), 'https://open.spotify.com/search/Maati')
        liked = plan_request('open Spotify and play my liked playlist')
        self.assertEqual(destination(liked.actions[0]), 'spotify:collection:tracks')
        liked_browser = plan_request('open Spotify and play my liked playlist', 'edge')
        self.assertEqual(destination(liked_browser.actions[0]), 'https://open.spotify.com/collection/tracks')

    def test_https_is_general_but_not_a_shell_or_credentials(self):
        self.assertEqual(plan_request('open https://example.org/path?').actions[0].target,
                         'https://example.org/path?')
        for value in ('http://example.org', 'javascript:alert(1)', 'file:///etc/passwd',
                      'https://user:pass@example.org', 'https://example.org\\evil',
                      'https://examp\u202ele.org', 'https://example.org:99999',
                      'https://example.org/\n', 'https://example.org/%0aevil'):
            with self.subTest(value=value), self.assertRaises(ActionError):
                validate_url(value)

    def test_ai_handles_and_mutations_cannot_be_forged(self):
        for data in ({'intent': 'file_workspace', 'query': '', 'path': 'victim'},
                     {'action': {'kind': 'installed_app', 'target': 'a' * 32, 'query': ''}},
                     {'intent': ['find_app'], 'query': ''}):
            with self.assertRaises(ProviderError):
                parse_proposal(json.dumps(data))

    def test_ai_url_must_be_present_in_transmitted_request(self):
        transport = Mock()
        def reply():
            proposal = {'action': {'kind': 'navigate', 'target': 'https://example.org/', 'query': ''}}
            return io.BytesIO(json.dumps({'message': {'content': json.dumps(proposal)}}).encode())
        transport.open.side_effect = lambda *a, **k: reply()
        provider = TextProvider(ProviderConfig('ollama', 'http://127.0.0.1:11434', 'm'), transport)
        with self.assertRaisesRegex(ProviderError, 'not explicitly'):
            provider.propose('download a useful tool')
        self.assertTrue(provider.propose('visit https://example.org/').actions)


class AppDiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.now = 0
        self.rows = [InstalledApp('My custom app', 'Vendor.Product_abcdefghijklm!App', True)]
        self.catalog = AppCatalog(lambda: tuple(self.rows), lambda: self.now)

    def test_inventory_rejects_paths_and_keeps_duplicate_names(self):
        rows = [{'Name': 'Same name', 'AppID': 'Vendor.One_abcd!App'},
                {'Name': 'Same name', 'AppID': 'Vendor.Two_abcd!App'},
                {'Name': 'Trap', 'AppID': 'C:\\evil.exe'},
                {'Name': 'Trap', 'AppID': 'foo,bar'},
                {'Name': 'Trap', 'AppID': 'foo&bar'}]
        self.assertEqual(len(parse_inventory(json.dumps({'Apps': rows, 'PackagedAppIds': []}))), 2)
        self.assertEqual(parse_inventory('{"Apps":[],"PackagedAppIds":[]}'), ())
        for raw in ('{}', 'null', '[{}]', 'x' * (2 * 1024 * 1024 + 1)):
            with self.assertRaises(DiscoveryError):
                parse_inventory(raw)

    def test_spoofed_packaged_shaped_shortcut_is_not_trusted(self):
        payload = {'Apps': [{'Name': 'Fake', 'AppID': 'Vendor.Product_abcdefghijklm!App'}],
                   'PackagedAppIds': []}
        self.assertFalse(parse_inventory(json.dumps(payload))[0].packaged)
        payload['PackagedAppIds'] = ['Vendor.Product_abcdefghijklm!App']
        self.assertTrue(parse_inventory(json.dumps(payload))[0].packaged)

    def test_scan_uses_constant_script_and_system_path(self):
        with patch('compcontrol.installed_apps.platform.system', return_value='Windows'), \
                patch('compcontrol.actions.system_directory', return_value=Path('/Windows/System32')), \
                patch('compcontrol.installed_apps.subprocess.run') as run:
            run.return_value = Mock(returncode=0, stdout=b'{"Apps":[],"PackagedAppIds":[]}')
            self.assertEqual(discover(), ())
            args, kw = run.call_args
            self.assertEqual(args[0][0], '/Windows/System32/WindowsPowerShell/v1.0/powershell.exe')
            self.assertIn('-NoProfile', args[0])
            self.assertFalse(kw['shell'])
            self.assertEqual(kw['timeout'], 12)

    def test_handles_expire_and_rescan_revokes(self):
        token, _ = self.catalog.scan()[0]
        self.now = 120
        with self.assertRaises(DiscoveryError):
            self.catalog.get(token)
        token, _ = self.catalog.scan()[0]
        self.catalog.scan()
        with self.assertRaises(DiscoveryError):
            self.catalog.get(token)

    @patch('compcontrol.actions.platform.system', return_value='Windows')
    @patch('compcontrol.actions.app_path', return_value=Path('/Windows/explorer.exe'))
    @patch('compcontrol.actions.subprocess.Popen')
    def test_selected_app_needs_approval_and_launches_once(self, popen, *_):
        token, _ = self.catalog.scan()[0]
        executor = WindowsExecutor(lambda *_: True, catalog=self.catalog)
        broker = Broker(executor)
        plan = broker.select_app(token)
        self.assertEqual(plan['title'], 'Launch My custom app')
        self.assertIn('Windows AppID:', plan['destinations'][0])
        self.assertNotIn('Vendor.Product', str(broker.state()))
        popen.assert_not_called()
        broker.confirm(plan['approval_id'])
        popen.assert_called_once_with(['/Windows/explorer.exe', 'shell:AppsFolder\\Vendor.Product_abcdefghijklm!App'],
                                      executable='/Windows/explorer.exe', cwd='/Windows', shell=False, close_fds=True)
        with self.assertRaises(BrokerError):
            broker.confirm(plan['approval_id'])

    @patch('compcontrol.actions.platform.system', return_value='Windows')
    @patch('compcontrol.actions.app_path', return_value=Path('/Windows/explorer.exe'))
    @patch('compcontrol.actions.subprocess.Popen')
    def test_changed_registration_or_decline_prevents_launch(self, popen, *_):
        token, _ = self.catalog.scan()[0]
        def changed(*_):
            self.rows.clear()
            return True
        broker = Broker(WindowsExecutor(changed, catalog=self.catalog))
        pending = broker.select_app(token)
        with self.assertRaises(BrokerError):
            broker.confirm(pending['approval_id'])
        popen.assert_not_called()

    def test_classic_shortcut_is_not_broker_launchable(self):
        classic = AppCatalog(lambda: (InstalledApp('Classic', 'Vendor.Classic'),))
        token, _ = classic.scan()[0]
        with self.assertRaisesRegex(BrokerError, '(?i)select the actual .exe'):
            Broker(WindowsExecutor(catalog=classic)).select_app(token)

    def test_ai_cannot_introduce_local_handle(self):
        token, _ = self.catalog.scan()[0]
        b = Broker(WindowsExecutor(catalog=self.catalog))
        ticket = b.begin_interpretation()
        with self.assertRaises(BrokerError):
            b.complete_interpretation(ticket, Plan('Forged', '', (Action('installed_app', token),)))

    @patch('compcontrol.actions.platform.system', return_value='Windows')
    @patch('compcontrol.actions.subprocess.Popen')
    def test_selected_executable_has_no_arguments_and_rechecks_hash(self, popen, *_):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'Custom.exe'
            path.write_bytes(b'MZ' + b'test fixture, not a real executable')
            token = self.catalog.add_executable(path)
            broker = Broker(WindowsExecutor(lambda *_: True, catalog=self.catalog))
            plan = broker.select_app(token)
            self.assertIn('SHA-256', plan['destinations'][0])
            broker.confirm(plan['approval_id'])
            popen.assert_called_once_with([str(path)], executable=str(path), cwd=str(path.parent), shell=False, close_fds=True)
            popen.reset_mock()
            token = self.catalog.add_executable(path)
            plan = broker.select_app(token)
            path.write_bytes(b'MZ changed')
            with self.assertRaises(BrokerError):
                broker.confirm(plan['approval_id'])
            popen.assert_not_called()

    def test_executable_scripts_links_and_classic_shortcuts_not_accepted(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'evil.cmd'
            path.write_bytes(b'MZblah')
            with self.assertRaises(WorkspaceError):
                select_executable(path)
        with self.assertRaises(DiscoveryError):
            self.catalog.revalidate(InstalledApp('Classic', 'Vendor.Classic'))


class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / 'project'
        self.root.mkdir()
        self.file = self.root / 'config.txt'
        self.file.write_bytes(b'color=green\nkeep=this\n')
        (self.root / 'config-other.txt').write_bytes(b'do not touch\n')

    def take(self):
        return snapshot(self.root, 'config.txt')

    def test_export_changes_neither_source_nor_similarly_named_file(self):
        before = {p: p.read_bytes() for p in self.root.iterdir()}
        review = preview_replace(self.take(), 'color=green', 'color=violet')
        self.assertIn(b'-color=green\n+color=violet', review.patch)
        dest = self.base / 'review.patch'
        export_patch(review, dest)
        self.assertEqual(dest.read_bytes(), review.patch)
        self.assertEqual(before, {p: p.read_bytes() for p in self.root.iterdir()})
        with self.assertRaises(WorkspaceError):
            export_patch(review, dest)
        with self.assertRaises(WorkspaceError):
            export_patch(review, self.root / 'new.patch')

    @patch('compcontrol.actions.platform.system', return_value='Windows')
    def test_patch_export_passes_through_broker_native_approval(self, _):
        original = self.take()
        patch = preview_replace(original, 'green', 'violet')
        destination = self.base / 'approved.patch'
        catalog = PatchCatalog()
        token = catalog.register(patch, destination)
        executor = WindowsExecutor(lambda *_: True, patch_catalog=catalog)
        broker = Broker(executor)
        offered = broker.offer_patch_export(token)
        self.assertIn(ascii(str(destination)), offered['destinations'][0])
        self.assertFalse(destination.exists())
        result = broker.confirm(offered['approval_id'])
        self.assertEqual(result['status'], 'executed')
        self.assertTrue(destination.exists())
        self.assertEqual(self.file.read_bytes(), b'color=green\nkeep=this\n')
        with self.assertRaises(BrokerError):
            broker.confirm(offered['approval_id'])

    @patch('compcontrol.actions.platform.system', return_value='Windows')
    def test_declining_or_staling_patch_approval_has_no_write(self, _):
        original = self.take()
        patch = preview_replace(original, 'green', 'violet')
        target = self.base / 'declined.patch'
        catalog = PatchCatalog()
        token = catalog.register(patch, target)
        broker = Broker(WindowsExecutor(lambda *_: False, patch_catalog=catalog))
        offered = broker.offer_patch_export(token)
        self.assertEqual(broker.confirm(offered['approval_id'])['status'], 'cancelled')
        self.assertFalse(target.exists())

        target = self.base / 'stale.patch'
        token = catalog.register(patch, target)
        broker = Broker(WindowsExecutor(lambda *_: True, patch_catalog=catalog))
        offered = broker.offer_patch_export(token)
        self.file.write_bytes(b'color=white\nkeep=this\n')
        with self.assertRaises(BrokerError):
            broker.confirm(offered['approval_id'])
        self.assertFalse(target.exists())
        self.assertEqual(self.file.read_bytes(), b'color=white\nkeep=this\n')

    def test_ai_cannot_forge_patch_handles(self):
        with self.assertRaises(ProviderError):
            parse_proposal(json.dumps({'action': {'kind': 'workspace_patch', 'target': 'a' * 32, 'query': ''}}))

    def test_case_traversal_ads_reserved_and_hidden_paths_rejected(self):
        for name in ('Config.txt', '../config.txt', '/config.txt', 'config.txt:stream',
                     'CON.txt', 'folder/../config.txt', 'config.txt.', 'config\u202e.txt'):
            with self.subTest(name=name), self.assertRaises(WorkspaceError):
                snapshot(self.root, name)

    def test_no_fuzzy_or_multi_match_edit(self):
        for old in ('absent', 'e', ''):
            with self.assertRaises(WorkspaceError):
                preview_replace(self.take(), old, 'new')
        self.file.write_bytes(b'aaa')
        with self.assertRaises(WorkspaceError):
            preview_replace(self.take(), 'aa', 'b')

    def test_source_change_invalidates_preview_and_export(self):
        original = self.take()
        review = preview_replace(original, 'green', 'violet')
        self.file.write_bytes(b'color=white\nkeep=this\n')
        for operation in (lambda: preview_replace(original, 'green', 'violet'),
                          lambda: export_patch(review, self.base / 'review.patch')):
            with self.assertRaisesRegex(WorkspaceError, 'changed'):
                operation()
        self.assertFalse((self.base / 'review.patch').exists())

    def test_replaced_same_content_invalidates_identity(self):
        original = self.take()
        replacement = self.root / 'replacement'
        replacement.write_bytes(self.file.read_bytes())
        os.replace(replacement, self.file)
        with self.assertRaises(WorkspaceError):
            preview_replace(original, 'green', 'violet')

    def test_binary_large_and_mixed_newlines(self):
        for data in (b'\x00bad', b'\xff', b'x' * (256 * 1024 + 1), b'a\r\nb\nc'):
            self.file.write_bytes(data)
            with self.assertRaises(WorkspaceError):
                self.take()

    def test_links_rejected(self):
        link = self.root / 'link.txt'
        try:
            link.symlink_to(self.file)
        except OSError:
            self.skipTest('Symlink creation unavailable')
        with self.assertRaises(WorkspaceError):
            snapshot(self.root, link.name)
        link.unlink()
        os.link(self.file, link)
        with self.assertRaises(WorkspaceError):
            self.take()

    def test_exported_patch_is_valid_for_crlf_and_no_final_newline(self):
        for source, old, new, expected in ((b'first\r\nsecond\r\n', 'second', 'new', b'first\r\nnew\r\n'),
                                           (b'first\nsecond', 'second', 'new', b'first\nnew')):
            self.file.write_bytes(source)
            review = preview_replace(self.take(), old, new)
            # Test apply in a DIFFERENT disposable copy. Product never applies patches.
            with tempfile.TemporaryDirectory() as copy:
                target = Path(copy) / 'config.txt'
                target.write_bytes(source)
                result = subprocess.run(['git', 'apply', '--unsafe-paths', '-'], input=review.patch,
                                        cwd=copy, capture_output=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(target.read_bytes(), expected)
                self.assertEqual(self.file.read_bytes(), source)
