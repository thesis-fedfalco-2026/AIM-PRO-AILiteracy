"""Offline native authoring JSON transport and failure-usage regression checks."""

import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import httpx
import main  # Configure vendor privacy before loading the provider.
from anthropic import Anthropic

from agent_system.anthropic import AnthropicJSONCompletion, IncompleteAnthropicOutput, usage_cost_usd
from agent_system.config import load_model_catalog
from agent_system.runtime import LLMFactory
from learning.contracts import Record


class TypedResult(Record):
    input_digest: str
    units: tuple[str, ...]


RATES = {'input': '3', 'output': '15', 'cache_write_5m': '3.75',
         'cache_write_1h': '6', 'cache_read': '.30'}


class AnthropicJSONTest(unittest.TestCase):
    def setUp(self):
        for target in ('socket.socket.connect', 'socket.create_connection', 'socket.getaddrinfo'):
            blocker = patch(target, side_effect=AssertionError('No network in Anthropic tests'))
            mock = blocker.start()
            self.addCleanup(blocker.stop)
            self.addCleanup(mock.assert_not_called)

    def stream(self, text, stop='end_turn', *, complete=True):
        events = [
            {'type': 'message_start', 'message': {'id': 'synthetic', 'type': 'message',
                'role': 'assistant', 'model': 'claude-sonnet-4-6', 'content': [],
                'stop_reason': None, 'stop_sequence': None, 'usage': {
                    'input_tokens': 24, 'output_tokens': 0, 'cache_creation_input_tokens': 30752,
                    'cache_read_input_tokens': 0, 'cache_creation': {
                        'ephemeral_5m_input_tokens': 30752, 'ephemeral_1h_input_tokens': 0}}}},
            {'type': 'content_block_start', 'index': 0, 'content_block': {'type': 'text', 'text': ''}},
            {'type': 'content_block_delta', 'index': 0, 'delta': {'type': 'text_delta', 'text': text}},
        ]
        if complete:
            events.extend([
                {'type': 'content_block_stop', 'index': 0},
                {'type': 'message_delta', 'delta': {'stop_reason': stop, 'stop_sequence': None},
                 'usage': {'output_tokens': 8000}},
                {'type': 'message_stop'}])
        return ''.join('event: ' + e['type'] + '\ndata: ' + json.dumps(e) + '\n\n' for e in events)

    def client(self, respond, *, stream=True):
        llm = AnthropicJSONCompletion(model='anthropic/claude-sonnet-4-6', api_key='synthetic',
            temperature=.1, top_p=.9, max_tokens=16000, stream=stream,
            thinking={'type': 'disabled'})
        http = httpx.Client(transport=httpx.MockTransport(respond))
        self.addCleanup(http.close)
        llm._client = Anthropic(api_key='synthetic', http_client=http, max_retries=0)
        self.addCleanup(llm._client.close)
        return llm

    def test_native_json_schema_without_tool_envelope(self):
        requests = []
        payload = {'input_digest': 'synthetic', 'units': ['complete content']}
        def respond(request):
            requests.append(json.loads(request.content))
            return httpx.Response(200, headers={'content-type': 'text/event-stream'},
                text=self.stream(json.dumps(payload)))
        llm = self.client(respond)
        result = llm.call('Produce typed authoring output', response_model=TypedResult)
        self.assertEqual(result.model_dump(mode='json'), payload)
        self.assertEqual(len(requests), 1)
        wire = requests[0]
        self.assertEqual(wire['model'], 'claude-sonnet-4-6')
        self.assertEqual(wire['max_tokens'], 16000)
        self.assertNotIn('tools', wire)
        self.assertNotIn('tool_choice', wire)
        self.assertNotIn('top_p', wire)
        self.assertEqual(wire['thinking'], {'type': 'disabled'})
        self.assertEqual(wire['output_config']['format']['type'], 'json_schema')
        self.assertIn('units', wire['output_config']['format']['schema']['required'])
        self.assertTrue(llm.completion_record()['usage_finalized'])

    def test_max_tokens_is_detected_before_parse_and_retains_cost(self):
        calls = []
        def respond(request):
            calls.append(request)
            return httpx.Response(200, headers={'content-type': 'text/event-stream'},
                text=self.stream('{"input_digest":"partial"', stop='max_tokens'))
        llm = self.client(respond)
        with self.assertRaises(IncompleteAnthropicOutput) as caught:
            llm.call('Produce output', response_model=TypedResult)
        self.assertEqual(caught.exception.stop_reason, 'max_tokens')
        record = llm.completion_record()
        self.assertEqual(record['raw_output'], '{"input_digest":"partial"')
        self.assertEqual(record['usage']['output_tokens'], 8000)
        self.assertEqual(usage_cost_usd(record, RATES), .235392)
        self.assertEqual(len(calls), 1)

    def test_schema_failure_after_end_turn_retains_usage(self):
        llm = self.client(lambda request: httpx.Response(200, headers={'content-type': 'text/event-stream'},
            text=self.stream('{"input_digest":"missing units"}')))
        with self.assertRaises(ValueError):
            llm.call('Produce output', response_model=TypedResult)
        self.assertEqual(llm.completion_record()['stop_reason'], 'end_turn')
        self.assertEqual(usage_cost_usd(llm.completion_record(), RATES), .235392)

    def test_incomplete_stream_has_no_fabricated_zero_cost(self):
        llm = self.client(lambda request: httpx.Response(200, headers={'content-type': 'text/event-stream'},
            text=self.stream('{"input_digest":', complete=False)))
        with self.assertRaises(IncompleteAnthropicOutput):
            llm.call('Produce output', response_model=TypedResult)
        self.assertFalse(llm.completion_record()['usage_finalized'])
        self.assertIsNone(usage_cost_usd(llm.completion_record(), RATES))

    def test_refusal_is_not_parsed_or_repaired(self):
        llm = self.client(lambda request: httpx.Response(200, headers={'content-type': 'text/event-stream'},
            text=self.stream('Synthetic refusal', stop='refusal')))
        with self.assertRaises(IncompleteAnthropicOutput) as caught:
            llm.call('Produce output', response_model=TypedResult)
        self.assertEqual(caught.exception.stop_reason, 'refusal')

    def test_http_failure_is_not_retried(self):
        calls = []
        def respond(request):
            calls.append(request)
            return httpx.Response(503, json={'type': 'error', 'error': {
                'type': 'overloaded_error', 'message': 'Synthetic overload'}})
        llm = self.client(respond)
        with self.assertRaises(Exception):
            llm.call('Produce output', response_model=TypedResult)
        self.assertEqual(len(calls), 1)
        self.assertIsNone(usage_cost_usd(llm.completion_record(), RATES))

    def test_nonstreaming_path_retains_native_schema_and_usage(self):
        requests = []
        def respond(request):
            requests.append(json.loads(request.content))
            return httpx.Response(200, json={'id': 'synthetic', 'type': 'message', 'role': 'assistant',
                'model': 'claude-sonnet-4-6', 'stop_reason': 'end_turn', 'stop_sequence': None,
                'content': [{'type': 'text', 'text': '{"input_digest":"synthetic","units":["complete"]}'}],
                'usage': {'input_tokens': 10, 'output_tokens': 20}})
        llm = self.client(respond, stream=False)
        self.assertEqual(llm.call('Output', response_model=TypedResult).units, ('complete',))
        self.assertEqual(usage_cost_usd(llm.completion_record(), RATES), .00033)
        self.assertIn('output_config', requests[0])

    def test_unclassified_cache_usage_has_unknown_cost(self):
        record = {'usage_finalized': True, 'usage': {'input_tokens': 1,
            'output_tokens': 1, 'cache_creation_input_tokens': 42}}
        self.assertIsNone(usage_cost_usd(record, RATES))

    def test_authoring_factory_opt_in_preserves_default_paid_guard(self):
        catalog = load_model_catalog(main.BASE_DIR / 'model.properties')
        factory = LLMFactory(catalog, environ={'ANTHROPIC_API_KEY': 'synthetic'}, anthropic_json_outputs=True)
        with self.assertRaisesRegex(ValueError, 'allow_paid'):
            factory('anthropic')
        catalog.profiles['anthropic'] = catalog.profiles['anthropic'].model_copy(update={'allow_paid': True})
        self.assertIsInstance(factory('anthropic'), AnthropicJSONCompletion)

    def test_authoring_builder_opts_in_for_lead_and_dispatcher_only(self):
        catalog = load_model_catalog(main.BASE_DIR / 'model.properties')
        catalog.profiles['openrouter'] = catalog.profiles['anthropic'].model_copy(update={'allow_paid': True})
        agents = []
        def agent(**kwargs):
            agents.append(kwargs)
            return SimpleNamespace(kickoff=lambda *args, **kw: self.fail('No model call is allowed'))
        dispatcher, lead, budget = main.build_aimpro_authoring(model_catalog=catalog,
            environ={'ANTHROPIC_API_KEY': 'synthetic'}, agent_factory=agent)
        self.assertIsInstance(agents[0]['llm'], AnthropicJSONCompletion)
        self.assertTrue(dispatcher.llm_factory.anthropic_json_outputs)
