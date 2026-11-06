"""Native JSON output for synchronous authoring, with failure-safe usage capture."""

from copy import deepcopy
from decimal import Decimal

from anthropic import transform_schema
from crewai.events.types.llm_events import LLMCallType
from crewai.llms.providers.anthropic.completion import AnthropicCompletion
from pydantic import BaseModel, PrivateAttr, model_validator


class IncompleteAnthropicOutput(ValueError):
    def __init__(self, stop_reason):
        self.stop_reason = stop_reason
        super().__init__('Anthropic structured output did not complete: ' + str(stop_reason))


def usage_cost_usd(record, rates):
    """Estimate completed response usage, including cache categories; unknown is not zero."""
    usage = record.get('usage', {})
    if not record.get('usage_finalized') or 'input_tokens' not in usage or 'output_tokens' not in usage:
        return None
    creation = usage.get('cache_creation') or {}
    five = creation.get('ephemeral_5m_input_tokens', 0)
    hour = creation.get('ephemeral_1h_input_tokens', 0)
    if five + hour != usage.get('cache_creation_input_tokens', 0):
        return None
    quantities = {'input': usage['input_tokens'], 'output': usage['output_tokens'],
        'cache_write_5m': five, 'cache_write_1h': hour,
        'cache_read': usage.get('cache_read_input_tokens', 0)}
    return float(sum(Decimal(str(rates[key])) * count for key, count in quantities.items()) / Decimal(1000000))


def typed_schema(schema):
    """Anthropic rejects untyped and recursive definitions such as pydantic's JsonValue.

    transform_schema closes free-form maps (dict[str, JsonValue]) to {}, so a
    proposal's Entity.fields cannot carry values through this path; only roles
    whose proposals stay empty are fully served.
    """
    scalar = {'anyOf': [{'type': t} for t in ('string', 'number', 'boolean', 'null')]}
    defs = {name: scalar if definition == {} else definition for name, definition in schema.get('$defs', {}).items()}
    return schema | {'$defs': defs} if defs else schema


def native_json_schema(response_model):
    """Build the exact wire schema; opt-in compaction never changes local validation.

    Nested nonempty arrays and optional object fields add grammar alternatives.
    Compact contracts require every property explicitly and leave array lower
    bounds to Pydantic. Keep descriptions (including bounds moved there by the
    SDK), typed fields, closed objects, references and union branches intact.
    This is an offline simplification, not a remote compiler acceptance check.
    """
    schema = transform_schema(typed_schema(response_model.model_json_schema()))
    if not getattr(response_model, 'compact_native_json_schema', False):
        return schema

    def compact(node):
        node.pop('title', None)
        minimum = node.pop('minItems', None)
        if minimum is not None:
            description = node.get('description', '')
            node['description'] = (description + '\n\n' if description else '') + '{minItems: ' + str(minimum) + '}'
        if node.get('type') == 'object':
            node['required'] = list(node['properties'])
        # Walk schema nodes only: property/definition names are arbitrary data.
        for key in ('$defs', 'properties'):
            for child in node.get(key, {}).values():
                compact(child)
        if 'items' in node:
            compact(node['items'])
        for key in ('anyOf', 'oneOf', 'allOf'):
            for child in node.get(key, []):
                compact(child)

    compact(schema)
    return schema


class AnthropicJSONCompletion(AnthropicCompletion):
    """Retain CrewAI dispatch/hooks, replacing its legacy tool-envelope JSON path."""

    max_retries: int = 0
    _completion_record: dict = PrivateAttr(default_factory=dict)

    @model_validator(mode='before')
    @classmethod
    def normalize_authoring_profile(cls, values):
        if not isinstance(values, dict):
            return values
        values = dict(values)
        if isinstance(values.get('model'), str):
            values['model'] = values['model'].removeprefix('anthropic/')
        if values.get('temperature') is not None:
            values.pop('top_p', None)
        return values

    def completion_record(self):
        return deepcopy(self._completion_record)

    def _prepare_completion_params(self, *args, **kwargs):
        params = super()._prepare_completion_params(*args, **kwargs)
        if params.get('thinking', {}).get('type') == 'disabled':
            params['thinking'] = {'type': 'disabled'}
        return params

    def _json_params(self, params, response_model, available_functions):
        if params.get('tools') or available_functions:
            raise ValueError('Native authoring JSON output does not execute tools')
        result = dict(params)
        result.pop('stream', None)
        result.pop('tool_choice', None)
        # Extra body supports the current API field without upgrading the installed SDK.
        result['extra_body'] = {'output_config': {'format': {
            'type': 'json_schema', 'schema': native_json_schema(response_model)}}}
        return result

    def _start_record(self):
        self._completion_record = {'format': 'native_json', 'raw_output': '',
            'usage': {}, 'stop_reason': None, 'stream_complete': False, 'usage_finalized': False}

    def _save_usage(self, usage):
        if usage is not None:
            values = usage.model_dump(exclude_none=True, exclude_unset=True) if hasattr(usage, 'model_dump') else usage
            self._completion_record['usage'].update(values)

    def _finish_json(self, response_model, params, from_task, from_agent):
        record = self._completion_record
        usage = record['usage']
        total_input = sum(usage.get(key, 0) for key in
            ('input_tokens', 'cache_creation_input_tokens', 'cache_read_input_tokens'))
        metrics = {'input_tokens': total_input, 'output_tokens': usage.get('output_tokens', 0),
            'total_tokens': total_input + usage.get('output_tokens', 0),
            'cached_prompt_tokens': usage.get('cache_read_input_tokens', 0),
            'cache_creation_tokens': usage.get('cache_creation_input_tokens', 0)}
        self._track_token_usage_internal(metrics)
        if not record['stream_complete'] or record['stop_reason'] != 'end_turn':
            raise IncompleteAnthropicOutput(record['stop_reason'])
        result = response_model.model_validate_json(record['raw_output'])
        self._emit_call_completed_event(response=result.model_dump_json(), call_type=LLMCallType.LLM_CALL,
            from_task=from_task, from_agent=from_agent, messages=params['messages'], usage=metrics,
            finish_reason=record['stop_reason'], response_id=record.get('response_id'))
        return result

    def _handle_streaming_completion(self, params, available_functions=None,
                                     from_task=None, from_agent=None, response_model=None):
        if not isinstance(response_model, type) or not issubclass(response_model, BaseModel):
            return super()._handle_streaming_completion(params, available_functions, from_task, from_agent, response_model)
        self._start_record()
        request = self._json_params(params, response_model, available_functions)
        with self._get_sync_client().messages.stream(**request) as stream:
            for event in stream:
                if event.type == 'message_start':
                    self._completion_record['response_id'] = event.message.id
                    self._save_usage(event.message.usage)
                elif event.type == 'content_block_delta' and event.delta.type == 'text_delta':
                    text = event.delta.text
                    self._completion_record['raw_output'] += text
                    self._emit_stream_chunk_event(chunk=text, from_task=from_task, from_agent=from_agent,
                        response_id=self._completion_record.get('response_id'))
                elif event.type == 'message_delta':
                    self._completion_record['stop_reason'] = event.delta.stop_reason
                    self._save_usage(event.usage)
                elif event.type == 'message_stop':
                    self._completion_record['stream_complete'] = True
                    self._completion_record['usage_finalized'] = 'output_tokens' in self._completion_record['usage']
        return self._finish_json(response_model, params, from_task, from_agent)

    def _handle_completion(self, params, available_functions=None,
                           from_task=None, from_agent=None, response_model=None):
        if not isinstance(response_model, type) or not issubclass(response_model, BaseModel):
            return super()._handle_completion(params, available_functions, from_task, from_agent, response_model)
        self._start_record()
        response = self._get_sync_client().messages.create(**self._json_params(params, response_model, available_functions))
        self._save_usage(response.usage)
        self._completion_record.update({'response_id': response.id, 'stop_reason': response.stop_reason,
            'raw_output': ''.join(block.text for block in response.content if block.type == 'text'),
            'stream_complete': True, 'usage_finalized': True})
        return self._finish_json(response_model, params, from_task, from_agent)
