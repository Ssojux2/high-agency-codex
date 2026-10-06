"""Execute the observer against native-shaped payload fixtures, without inference."""
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / 'plugins/high-agency'
SCRIPT = PLUGIN / 'hooks/routing_observer.py'
HOST = 'claude' if (PLUGIN / '.claude-plugin').is_dir() else 'codex'


class ObserverRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.env = dict(os.environ, TMPDIR=str(self.directory), TEMP=str(self.directory),
                        TMP=str(self.directory), PLUGIN_DATA=str(self.directory / 'plugin-data'),
                        PYTHONDONTWRITEBYTECODE='1')

    def run_script(self, *args, payload=None):
        proc = subprocess.run([sys.executable, '-B', str(SCRIPT), *args],
                              input=json.dumps(payload) if payload is not None else '',
                              capture_output=True, text=True, env=self.env, timeout=10)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stderr, '')
        return proc.stdout

    def event(self, call='call-1', session='session-1'):
        args = ({'model': 'haiku', 'subagent_type': 'high-agency:high-agency-scout'} if HOST == 'claude'
                else {'model': 'gpt-6.1-sol', 'reasoning_effort': 'high', 'agent_type': 'default'})
        args['prompt'] = 'PRIVATE_PROMPT_DO_NOT_STORE'
        response = ({'status': 'completed', 'agentId': 'child-1', 'resolvedModel': 'claude-haiku-4-5',
                     'modelsUsed': ['claude-haiku-4-5'], 'content': [{'type': 'text', 'text': 'PRIVATE_ANSWER_DO_NOT_STORE'}]}
                    if HOST == 'claude' else {'agent_id': 'child-1'})
        return {'hook_event_name': 'PostToolUse', 'session_id': session, 'tool_use_id': call,
                'tool_name': 'Agent' if HOST == 'claude' else 'spawn_agent',
                'model': 'PARENT_MODEL_DO_NOT_USE', 'tool_input': args, 'tool_response': response}

    def read_report(self, session='session-1'):
        args = ['--report'] + (['--session-id', session] if session is not None else [])
        return json.loads(self.run_script(*args))

    def test_observes_request_and_native_dispatch_without_copying_content(self):
        self.assertEqual(self.run_script(payload=self.event()), '')
        report = self.read_report()
        self.assertEqual(report['host'], HOST)
        self.assertEqual(report['observation_status'], 'observed')
        record = report['records'][0]
        self.assertEqual(record['requested']['model_source'], 'tool_input.model')
        self.assertEqual(record['child_id'], 'child-1')
        self.assertEqual(record['dispatch_status'], 'completed' if HOST == 'claude' else 'launched')
        self.assertEqual(record['freshness_status'], 'unverified')
        self.assertEqual(record['effort_status'], 'unverified')
        saved = '\n'.join(path.read_text() for path in self.directory.rglob('*.json'))
        for secret in ('PRIVATE_PROMPT_DO_NOT_STORE', 'PRIVATE_ANSWER_DO_NOT_STORE', 'PARENT_MODEL_DO_NOT_USE'):
            self.assertNotIn(secret, saved)

    def test_utf8_input_is_independent_of_the_text_stream_locale(self):
        session = 'session-한글'
        self.env['PYTHONIOENCODING'] = 'cp1252'
        wire = json.dumps(self.event(session=session), ensure_ascii=False).encode('utf-8')
        proc = subprocess.run([sys.executable, '-B', str(SCRIPT)], input=wire,
                              capture_output=True, env=self.env, timeout=10)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stderr, b'')
        report = self.read_report(session)
        self.assertEqual(report['observation_status'], 'observed')
        self.assertEqual(report['records'][0]['child_id'], 'child-1')

    def test_missing_metadata_does_not_inherit_parent_or_parse_agent_prose(self):
        event = self.event()
        event['tool_input'] = {'prompt': 'PRIVATE_PROMPT_DO_NOT_STORE'}
        event['tool_response'] = {'agentId': 'child-1', 'agent_id': 'child-1', 'status': 'completed',
                                 'model': 'parent-or-unknown-model',
                                 'content': [{'type': 'text', 'text': '{"modelsUsed":["pretend-served"]}'}]}
        self.run_script(payload=event)
        record = self.read_report()['records'][0]
        self.assertIsNone(record['requested']['model'])
        self.assertIsNone(record['resolvedModel'])
        self.assertEqual(record['modelsUsed'], [])
        self.assertEqual(record['served_model_status'], 'unverified')
        self.assertEqual(record['entitlement_status'], 'unverified')

    def test_no_session_report_does_not_select_another_session(self):
        self.run_script(payload=self.event())
        report = self.read_report(None)
        self.assertEqual(report['scope'], 'unspecified')
        self.assertEqual(report['observation_status'], 'unverified')
        self.assertEqual(report['records'], [])
        self.assertEqual(self.read_report('another-session')['records'], [])

    def test_unrelated_and_malformed_events_are_silent_and_do_not_write(self):
        for payload in ({}, [], {'hook_event_name': {}}, {'hook_event_name': 'PostToolUse', 'tool_name': []},
                        {'hook_event_name': 'PostToolUse', 'tool_name': 'Bash', 'session_id': 's'}):
            self.assertEqual(self.run_script(payload=payload), '')
        self.assertEqual(list(self.directory.rglob('*.json')), [])

    def test_parallel_delegations_preserve_all_observations(self):
        with ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(lambda n: self.run_script(payload=self.event('call-' + str(n))), range(12)))
        records = self.read_report()['records']
        self.assertEqual({record['tool_use_id'] for record in records}, {'call-' + str(n) for n in range(12)})

    def test_unknown_response_shape_does_not_claim_completed_serving(self):
        event = self.event()
        event['tool_response'] = {'status': {'unexpected': True}, 'resolvedModel': 'pretend-served',
                                 'modelsUsed': ['pretend-served']}
        self.run_script(payload=event)
        record = self.read_report()['records'][0]
        self.assertEqual(record['dispatch_status'], 'response_observed')
        self.assertEqual(record['served_model_status'], 'unverified')

    @unittest.skipUnless(HOST == 'claude', 'Claude native AgentOutput metadata')
    def test_native_swap_metadata_is_distinct_from_requested_alias(self):
        event = self.event()
        event['tool_response']['resolvedModel'] = 'claude-sonnet-4-6'
        event['tool_response']['modelsUsed'] = ['claude-haiku-4-5', 'claude-sonnet-4-6']
        self.run_script(payload=event)
        record = self.read_report()['records'][0]
        self.assertEqual(record['requested']['model'], 'haiku')
        self.assertEqual(record['resolvedModel'], 'claude-sonnet-4-6')
        self.assertEqual(record['served_model_status'], 'host_reported')
        self.assertEqual(record['fallback_status'], 'multiple_models_observed')
        self.assertIsNone(record['fallback_reason'])
        self.assertEqual(record['entitlement_status'], 'observed_for_completed_dispatch')

    @unittest.skipUnless(HOST == 'claude', 'Claude native AgentOutput metadata')
    def test_async_resolution_alone_does_not_prove_serving_or_completion(self):
        event = self.event()
        event['tool_response']['status'] = 'async_launched'
        event['tool_response'].pop('modelsUsed')
        self.run_script(payload=event)
        record = self.read_report()['records'][0]
        self.assertEqual(record['dispatch_status'], 'async_launched')
        self.assertEqual(record['resolution_status'], 'host_reported')
        self.assertEqual(record['served_model_status'], 'unverified')
        self.assertEqual(record['entitlement_status'], 'unverified')

    @unittest.skipUnless(HOST == 'claude', 'Claude role frontmatter defaults')
    def test_role_default_is_labelled_as_requested_policy(self):
        event = self.event()
        event['tool_input'].pop('model')
        self.run_script(payload=event)
        requested = self.read_report()['records'][0]['requested']
        self.assertEqual(requested['model'], 'haiku')
        self.assertEqual(requested['model_source'], 'bundled_role_frontmatter')
        self.assertEqual(requested['effort'], 'low')
        self.assertEqual(requested['effort_source'], 'bundled_role_frontmatter')

    @unittest.skipUnless(HOST == 'claude', 'Claude PostToolUseFailure event')
    def test_rejected_dispatch_does_not_record_response_models_or_error_text(self):
        event = self.event()
        event['hook_event_name'] = 'PostToolUseFailure'
        event['error'] = 'PRIVATE_ERROR_DO_NOT_STORE'
        self.run_script(payload=event)
        report = self.read_report()
        record = report['records'][0]
        self.assertEqual(record['dispatch_status'], 'failed')
        self.assertEqual(record['modelsUsed'], [])
        self.assertEqual(record['served_model_status'], 'unverified')
        self.assertNotIn('PRIVATE_ERROR_DO_NOT_STORE', json.dumps(report))

    @unittest.skipUnless(HOST == 'codex', 'Codex has no supported child serving metadata adapter')
    def test_codex_observes_request_but_rejects_uncontracted_served_model_fields(self):
        event = self.event()
        event['tool_response'].update({'resolvedModel': 'pretend-served', 'modelsUsed': ['pretend-served']})
        self.run_script(payload=event)
        report = self.read_report()
        record = report['records'][0]
        self.assertEqual(report['capabilities']['request_observation'], 'supported')
        self.assertEqual(report['capabilities']['models_used_metadata'], 'unsupported')
        self.assertEqual(record['requested']['effort'], 'high')
        self.assertEqual(record['modelsUsed'], [])
        self.assertEqual(record['served_model_status'], 'unverified')

    @unittest.skipUnless(HOST == 'codex', 'Codex plugin data is supplied by the host')
    def test_missing_plugin_data_never_writes_into_project(self):
        self.env.pop('PLUGIN_DATA')
        self.assertEqual(self.run_script(payload=self.event()), '')
        self.assertEqual(self.read_report()['records'], [])


if __name__ == '__main__':
    unittest.main()
