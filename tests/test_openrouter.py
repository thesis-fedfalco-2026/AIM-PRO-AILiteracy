import json
import time
import unittest
from unittest.mock import patch

import httpx
from openai import APIError, OpenAI

import main
from agent_system.config import ConfigurationError, load_model_catalog
from agent_system.plan import ExecutionPlan
from agent_system.runtime import LLMFactory


class OpenRouterTest(unittest.TestCase):
    def factory(self, model=None, *, allow_paid=False):
        catalog = load_model_catalog(main.BASE_DIR / 'model.properties')
        if model is not None:
            catalog.profiles['openrouter'] = catalog.profiles['openrouter'].model_copy(
                update={'model': model, 'allow_paid': allow_paid})
        return LLMFactory(catalog, environ={'OPENROUTER_API_KEY': 'test'})

    def test_paid_openrouter_model_requires_explicit_opt_in(self):
        with self.assertRaisesRegex(ConfigurationError, 'allow_paid = true'):
            self.factory('nvidia/nemotron-3-super-120b-a12b').validate({'openrouter'})

    def test_paid_openrouter_model_has_no_free_price_cap(self):
        paid = self.factory('nvidia/nemotron-3-super-120b-a12b', allow_paid=True)
        paid.validate({'openrouter'})
        llm = paid('openrouter')
        requests = []

        def respond(request):
            requests.append(json.loads(request.content))
            chunk = {'id': 'test', 'object': 'chat.completion.chunk', 'created': 1,
                     'model': 'nvidia/nemotron-3-super-120b-a12b',
                     'choices': [{'index': 0, 'delta': {'role': 'assistant', 'content': 'OK'},
                                  'finish_reason': 'stop'}]}
            return httpx.Response(200, headers={'content-type': 'text/event-stream'},
                                  text='data: ' + json.dumps(chunk) + '\n\ndata: [DONE]\n\n')

        with OpenAI(api_key='test', base_url='https://openrouter.ai/api/v1',
                    http_client=httpx.Client(transport=httpx.MockTransport(respond))) as client:
            llm._client = client
            self.assertEqual(llm.call([{'role': 'user', 'content': 'Answer'}]), 'OK')
        self.assertNotIn('provider', requests[0])

    def test_stream_failure_retries_before_returning_validated_plan(self):
        requests = []

        def respond(request):
            requests.append(json.loads(request.content))
            prefix = ''
            if len(requests) == 1:
                partial = {
                    'id': 'interrupted', 'object': 'chat.completion.chunk', 'created': 1,
                    'model': 'test:free', 'choices': [{'index': 0,
                    'delta': {'role': 'assistant', 'content': '{"steps":['},
                    'finish_reason': None}],
                }
                prefix = 'data: ' + json.dumps(partial) + '\n\n'
                chunk = {'error': {'code': 502, 'message': 'PRIVATE provider failure'}}
            else:
                chunk = {
                    'id': 'test', 'object': 'chat.completion.chunk', 'created': 1,
                    'model': 'test:free', 'choices': [{'index': 0,
                    'delta': {'role': 'assistant', 'content': '{"steps":[]}'},
                    'finish_reason': 'stop'}],
                }
            return httpx.Response(200, headers={'content-type': 'text/event-stream'},
                                  text=prefix + 'data: ' + json.dumps(chunk) + '\n\ndata: [DONE]\n\n')

        llm = self.factory()('openrouter')
        with OpenAI(api_key='test', base_url='https://openrouter.ai/api/v1',
                    http_client=httpx.Client(transport=httpx.MockTransport(respond))) as client:
            llm._client = client
            with patch('time.sleep'):
                result = llm.call([{'role': 'user', 'content': 'Plan'}],
                                  response_model=ExecutionPlan)
        self.assertEqual(result, ExecutionPlan(steps=()))
        self.assertEqual(len(requests), 2)
        self.assertEqual(requests[0]['provider']['max_price'], {'prompt': 0, 'completion': 0})

    def test_keep_alive_stream_fails_at_wall_clock_deadline(self):
        # OpenRouter keeps a queued request alive with SSE comments, which reset
        # httpx's per-read timeout; only the request deadline ends it.
        factory = self.factory()
        settings = factory.catalog.settings.model_copy(update={'timeout': 0.3})
        llm = factory('openrouter', settings)
        chunks = []

        def keep_alive():
            while True:
                chunks.append(time.sleep(0.05))
                yield b': OPENROUTER PROCESSING\n\n'

        def respond(transport, request):
            return httpx.Response(200, headers={'content-type': 'text/event-stream'}, content=keep_alive())

        started = time.monotonic()
        with patch('httpx.HTTPTransport.handle_request', respond), self.assertRaises(Exception) as raised:
            llm.call([{'role': 'user', 'content': 'Answer'}])
        self.assertLess(time.monotonic() - started, 2)
        self.assertLess(len(chunks), 20)
        self.assertIn('wall-clock deadline', repr(raised.exception) + repr(raised.exception.__cause__))

    def test_permanent_stream_error_is_not_retried_and_transient_is_bounded(self):
        for code, attempts in ((401, 1), (402, 1), (400, 1), (408, 3), (429, 3),
                               (500, 3), (502, 3), (503, 3), (504, 3)):
            with self.subTest(code=code):
                requests = []

                def respond(request):
                    requests.append(request)
                    return httpx.Response(200, headers={'content-type': 'text/event-stream'},
                        text='data: ' + json.dumps({'error': {'code': code, 'message': 'PRIVATE'}}) + '\n\n')

                llm = self.factory()('openrouter')
                with OpenAI(api_key='test', base_url='https://openrouter.ai/api/v1',
                            http_client=httpx.Client(transport=httpx.MockTransport(respond))) as client:
                    llm._client = client
                    with patch('time.sleep'), self.assertRaises(APIError):
                        llm.call([{'role': 'user', 'content': 'Answer'}])
                self.assertEqual(len(requests), attempts)
