import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'plugins/high-agency/scripts/model_catalog.py'
spec = importlib.util.spec_from_file_location('catalog', SCRIPT)
catalog = importlib.util.module_from_spec(spec)
spec.loader.exec_module(catalog)


def model(name, efforts=('low', 'medium', 'high'), **extra):
    return {'model': name, 'defaultReasoningEffort': 'medium',
            'supportedReasoningEfforts': [{'reasoningEffort': e} for e in efforts], **extra}


class ResolverTests(unittest.TestCase):
    def test_latest_version_of_each_family(self):
        models = [model('gpt-5.6-sol'), model('gpt-6-sol'), model('gpt-6.1-sol'),
                  model('gpt-5.6-luna'), model('gpt-6-luna'), model('gpt-6-astra')]
        routes = catalog.resolve(models)
        self.assertEqual(routes['WORKHORSE']['model'], 'gpt-6.1-sol')
        self.assertEqual(routes['BROAD MAP']['model'], 'gpt-6.1-sol')
        self.assertEqual(routes['CHEAP DELEGATE']['model'], 'gpt-6-luna')
        self.assertEqual(routes['STRONG REASONING']['model'], 'gpt-6-astra')

    def test_future_versions_do_not_require_code_updates(self):
        routes = catalog.resolve([model('gpt-12.9-sol'), model('gpt-12.10-sol')])
        self.assertEqual(routes['WORKHORSE']['model'], 'gpt-12.10-sol')

    def test_version_and_snapshot_order(self):
        names = ['gpt-6-sol-2026-09-01', 'gpt-6.0-sol-2026-09-02', 'gpt-6.1-sol-2026-01-01']
        self.assertEqual(catalog.resolve([model(n) for n in names])['WORKHORSE']['model'], names[-1])

    def test_unavailable_hidden_preview_and_deprecated_excluded(self):
        models = [model('gpt-6-sol'), model('gpt-7-sol', hidden=True),
                  model('gpt-8-sol', available=False), model('gpt-9-sol', disabled=True),
                  model('gpt-10-sol-preview'), model('gpt-11-sol', preview=True),
                  model('gpt-12-sol', deprecated=True)]
        self.assertEqual(catalog.resolve(models)['WORKHORSE']['model'], 'gpt-6-sol')

    def test_rejected_model_is_not_selected_again(self):
        models = [model('gpt-6.1-sol'), model('gpt-6-sol')]
        self.assertEqual(catalog.resolve(models, ('gpt-6.1-sol',))['WORKHORSE']['model'], 'gpt-6-sol')

    def test_fallback_families(self):
        routes = catalog.resolve([model('gpt-5.6-terra')])
        self.assertEqual(routes['CHEAP DELEGATE']['model'], 'gpt-5.6-terra')
        self.assertEqual(routes['BROAD MAP']['model'], 'gpt-5.6-terra')
        self.assertIsNone(routes['WORKHORSE']['model'])
        self.assertEqual(routes['WORKHORSE']['fallback'], 'current main model')

    def test_empty_or_unknown_families_keep_current(self):
        for models in ([], [model('future-provider-model')]):
            for route in catalog.resolve(models).values():
                self.assertIsNone(route['model'])
                self.assertEqual(route['fallback'], 'current main model')

    def test_effort_is_never_invented(self):
        item = model('gpt-6-astra', ('low', 'medium'))
        route = catalog.resolve([item])['STRONG REASONING']
        self.assertEqual(route['reasoning_effort'], 'medium')
        self.assertIn(route['reasoning_effort'], route['supported_reasoning_efforts'])
        self.assertIsNone(catalog.supported_effort({'model': 'gpt-6-sol'}, 'max'))

    def test_advertised_default_is_used_when_lower_missing(self):
        item = model('gpt-6-luna', ('high',), defaultReasoningEffort='high')
        self.assertEqual(catalog.supported_effort(item, 'low'), 'high')

    def test_malformed_effort_capabilities_do_not_crash(self):
        for value in (None, 3, {}, 'high', [None, 'bad']):
            item = {'model': 'gpt-6-sol', 'supportedReasoningEfforts': value}
            self.assertIsNone(catalog.resolve([item])['WORKHORSE']['reasoning_effort'])

    def test_page_validation(self):
        for value in (None, [], {}, {'data': {}}):
            with self.assertRaises(ValueError):
                catalog.models_from_page(value)


class ProtocolTests(unittest.TestCase):
    def fake(self, source, timeout=2):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'fake_server.py'
            path.write_text(source)
            return catalog.read_live([sys.executable, '-u', str(path)], timeout)

    def test_handshake_pagination_and_metadata_only(self):
        result = self.fake('''import json, sys
for line in sys.stdin:
    request = json.loads(line)
    method = request['method']
    assert method in ('initialize', 'initialized', 'model/list'), method
    if method == 'initialized':
        continue
    if method == 'initialize':
        assert request['id'] == 1
        result = {}
    else:
        assert request['params']['includeHidden'] is False
        cursor = request['params'].get('cursor')
        result = {'data': [{'model': 'gpt-6-sol' if cursor is None else 'gpt-6.1-sol'}],
                  'nextCursor': 'page2' if cursor is None else None}
    print('not json', flush=True)
    print(json.dumps({'method': 'notification'}), flush=True)
    print(json.dumps({'id': request['id'], 'result': result}), flush=True)
''')
        self.assertEqual([item['model'] for item in result], ['gpt-6-sol', 'gpt-6.1-sol'])

    def test_repeated_cursor_fails(self):
        with self.assertRaisesRegex(ValueError, 'cursor'):
            self.fake('''import json, sys
for line in sys.stdin:
    r = json.loads(line)
    if 'id' in r:
        result = {} if r['method'] == 'initialize' else {'data': [], 'nextCursor': 'again'}
        print(json.dumps({'id': r['id'], 'result': result}), flush=True)
''')

    def test_server_error_is_redacted(self):
        with self.assertRaisesRegex(ValueError, '^model catalog request rejected$'):
            self.fake('''import json, sys
r = json.loads(sys.stdin.readline())
print(json.dumps({'id': r['id'], 'error': {'message': 'sensitive configuration'}}), flush=True)
''')

    def test_timeout_is_bounded(self):
        start = time.monotonic()
        with self.assertRaises(TimeoutError):
            self.fake('import time; time.sleep(60)', timeout=0.15)
        self.assertLess(time.monotonic() - start, 3)

    def test_invalid_timeout(self):
        for timeout in (0, -1, float('nan'), float('inf')):
            with self.assertRaises(ValueError):
                catalog.read_live(['does-not-exist'], timeout)

    def test_closed_connection_fails(self):
        with self.assertRaises(ValueError):
            self.fake('pass')


class CommandTests(unittest.TestCase):
    def run_cli(self, payload, *args):
        return subprocess.run([sys.executable, str(SCRIPT), '--catalog', '-', *args],
                              input=json.dumps(payload), capture_output=True, text=True, timeout=3)

    def test_supplied_catalog(self):
        proc = self.run_cli({'data': [model('gpt-6.1-sol')], 'nextCursor': None})
        self.assertEqual(proc.returncode, 0, proc.stderr)
        data = json.loads(proc.stdout)
        self.assertIn('not independently verified', data['freshness'])
        self.assertEqual(data['routes']['WORKHORSE']['model'], 'gpt-6.1-sol')

    def test_rpc_envelope_and_exclusion(self):
        proc = self.run_cli({'result': {'data': [model('gpt-6.1-sol'), model('gpt-6-sol')]}},
                            '--exclude-model', 'gpt-6.1-sol')
        self.assertEqual(json.loads(proc.stdout)['routes']['WORKHORSE']['model'], 'gpt-6-sol')

    def test_incomplete_catalog_fails_closed(self):
        proc = self.run_cli({'data': [model('gpt-6-sol')], 'nextCursor': 'more'})
        self.assertEqual(proc.returncode, 2)
        self.assertIsNone(json.loads(proc.stdout)['routes']['WORKHORSE']['model'])

    def test_missing_binary_gives_safe_fallback(self):
        proc = subprocess.run([sys.executable, str(SCRIPT), '--codex-bin', '/no-such-codex-binary'],
                              capture_output=True, text=True, timeout=3)
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(json.loads(proc.stdout)['source'], 'unavailable')
        self.assertNotIn('Traceback', proc.stderr)

    def test_manifests_agree(self):
        a = json.loads((ROOT / 'plugins/high-agency/plugin.json').read_text())
        b = json.loads((ROOT / 'plugins/high-agency/.codex-plugin/plugin.json').read_text())
        self.assertEqual(a['version'], b['version'])


if __name__ == '__main__':
    unittest.main()
