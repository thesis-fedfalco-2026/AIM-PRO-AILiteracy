"""Optional tracing boundary. Disabled mode imports no telemetry SDKs."""
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps
import base64
import hashlib
import hmac
import json
import logging
import os
from pathlib import Path
import subprocess
from urllib.parse import urlparse

_client = None
_salt = b""
_synthetic = False
_subjects = {}
_learning = ContextVar("telemetry_learning", default=False)
_logger = logging.getLogger("agent_system.telemetry")


def configure_vendor_privacy(base_dir):
    """Isolate vendor consent locally; never change machine-wide preferences."""
    storage = Path(base_dir).resolve() / ".cache" / "crewai"
    storage.mkdir(parents=True, exist_ok=True)
    os.environ["CREWAI_STORAGE_DIR"] = str(storage)
    os.environ["CREWAI_DISABLE_TELEMETRY"] = "true"
    os.environ["CREWAI_TRACING_ENABLED"] = "false"
    # CrewAI 1.15 falls back to saved consent even when the env value is false.
    # A local declined-consent record also disables first-run cloud collection.
    path = storage / ".crewai_user.json"
    path.write_text(json.dumps({"trace_consent": False, "first_execution_done": True}))


def data(value):
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if hasattr(value, "fields"):
        return value.fields
    if isinstance(value, dict):
        return {str(k): data(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [data(v) for v in value]
    return value


def mask(value=None, **kwargs):
    """Redact structured identity fields and identities embedded in prompts/JSON."""
    value = data(kwargs.get("data", value))
    if isinstance(value, dict):
        return {k: ("[REDACTED]" if k.lower() in {
            "subject_key", "subjectkey", "api_key", "authorization", "secret_key"
        } else mask(v)) for k, v in value.items()}
    if isinstance(value, list):
        return [mask(v) for v in value]
    if isinstance(value, str):
        for raw, hashed in sorted(tuple(_subjects.items()), key=lambda item: -len(item[0])):
            value = value.replace(raw, hashed)
            value = value.replace(json.dumps(raw, ensure_ascii=True)[1:-1], hashed)
        return value
    return value


def initialize(environ=None, *, span_exporter=None):
    global _client, _salt, _synthetic
    env = os.environ if environ is None else environ
    if env.get("LANGFUSE_ENABLED", "").lower() not in {"true", "1"} or _client is not None:
        return
    base = env.get("LANGFUSE_BASE_URL", "")
    host = urlparse(base).hostname
    if not host or urlparse(base).scheme not in {"http", "https"}:
        raise ValueError("Set an explicit LANGFUSE_BASE_URL")
    if (host == "langfuse.com" or host.endswith(".langfuse.com")) and env.get("LANGFUSE_SYNTHETIC_DATA_ONLY") != "true":
        raise ValueError("Langfuse Cloud requires synthetic data only")
    if not all(env.get(k) for k in ("LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY", "LANGFUSE_HASH_SALT")):
        raise ValueError("Langfuse keys and LANGFUSE_HASH_SALT are required")
    from langfuse import Langfuse
    from langfuse.types import MaskOtelSpansResult, OtelSpanPatch
    from opentelemetry.sdk.trace import Event, ReadableSpan, SpanProcessor, TracerProvider
    from opentelemetry.sdk.trace.export import SpanExporter
    from opentelemetry.trace import Status
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from openinference.instrumentation.crewai import CrewAIInstrumentor
    from openinference.instrumentation.openai import OpenAIInstrumentor

    class PrivacyProcessor(SpanProcessor):
        def on_start(self, span, parent_context=None):
            span.set_attribute("alm.private_content", _learning.get())

    def mask_spans(*, params):
        patches = {}
        for key, span in params.spans.items():
            attrs = span.attributes
            private = attrs.get("alm.private_content", False)
            updates = {}
            for name, value in attrs.items():
                if private and any(part in name.lower() for part in
                                   ("input", "output", "prompt", "completion", "message", "exception", "document")):
                    updates[name] = "[REDACTED: LEARNING]"
                else:
                    updates[name] = mask(value)
            patches[key] = OtelSpanPatch(set_attributes=updates)
        return MaskOtelSpansResult(span_patches=patches)

    # The SDK mask hook covers attributes. Sanitize exception events, span names
    # and status descriptions too, since third-party instrumentors can set them.
    destination = span_exporter
    if destination is None:
        auth = base64.b64encode((env["LANGFUSE_PUBLIC_KEY"] + ":" + env["LANGFUSE_SECRET_KEY"]).encode()).decode()
        destination = OTLPSpanExporter(endpoint=base.rstrip("/") + "/api/public/otel/v1/traces",
                                       headers={"Authorization": "Basic " + auth})

    class PrivateExporter(SpanExporter):
        def export(self, spans):
            sanitized = []
            for span in spans:
                private = span.attributes.get("alm.private_content", False)
                events = [Event(mask(event.name), attributes={k: "[REDACTED: LEARNING]" if private else mask(v)
                                for k, v in event.attributes.items()}, timestamp=event.timestamp) for event in span.events]
                sanitized.append(ReadableSpan(name=mask(span.name), context=span.context, parent=span.parent,
                    resource=span.resource, attributes=span.attributes, events=events, links=span.links,
                    kind=span.kind, status=Status(span.status.status_code,
                        "[REDACTED: LEARNING]" if private and span.status.description else mask(span.status.description)),
                    start_time=span.start_time, end_time=span.end_time, instrumentation_scope=span.instrumentation_scope))
            return destination.export(sanitized)

        def shutdown(self):
            destination.shutdown()

        def force_flush(self, timeout_millis=30000):
            return destination.force_flush(timeout_millis)

    _synthetic = env.get("LANGFUSE_SYNTHETIC_DATA_ONLY") == "true"
    _salt = env["LANGFUSE_HASH_SALT"].encode()
    provider = TracerProvider()
    provider.add_span_processor(PrivacyProcessor())
    _client = Langfuse(public_key=env["LANGFUSE_PUBLIC_KEY"], secret_key=env["LANGFUSE_SECRET_KEY"],
                       base_url=base, tracer_provider=provider, mask=mask, mask_otel_spans=mask_spans,
                       span_exporter=PrivateExporter())
    CrewAIInstrumentor().instrument(skip_dep_check=True, tracer_provider=provider)
    OpenAIInstrumentor().instrument(tracer_provider=provider)


class Observation:
    def __init__(self, span=None):
        self.span = span

    def update(self, **values):
        if self.span is not None:
            try:
                self.span.update(**mask(data(values)))
            except Exception:
                _logger.warning("Telemetry update unavailable")

    def score(self, name, value, reason=None):
        if self.span is not None:
            try:
                self.span.score(name=name, value=value, data_type="CATEGORICAL", comment="[REDACTED: LEARNING]" if _learning.get() and reason else mask(reason))
            except Exception:
                _logger.warning("Telemetry score unavailable")


@contextmanager
def observation(name, kind="span", **values):
    if _client is None:
        yield Observation()
        return
    # Enter failures must not prevent the application from handling the request.
    try:
        manager = _client.start_as_current_observation(name=name, as_type=kind, **mask(data(values)))
        span = manager.__enter__()
    except Exception:
        _logger.warning("Telemetry unavailable")
        yield Observation()
        return
    try:
        yield Observation(span)
    except Exception as error:
        Observation(span).update(level="ERROR", status_message=mask(str(error)))
        raise
    finally:
        try:
            manager.__exit__(None, None, None)
        except Exception:
            _logger.warning("Telemetry export unavailable")


def traced(name, kind="span", inputs=None):
    def decorate(function):
        @wraps(function)
        def wrapper(*args, **kwargs):
            with observation(name, kind, input=inputs(*args, **kwargs) if inputs else None) as span:
                try:
                    result = function(*args, **kwargs)
                except Exception as error:
                    if kind == "guardrail":
                        span.score(name, "REJECT", str(error))
                    raise
                if name == "authorize_plan":
                    span.update(output={"accepted_steps": [task.step.id for task in result]})
                    span.score(name, "ACCEPT")
                else:
                    span.update(output=data(result))
                    if kind == "guardrail":
                        status = result.fields["status"] if hasattr(result, "fields") else (
                            "FAILED" if result.kind == "FAILURE" else "SUCCEEDED")
                        span.score(name, status)
                        span.update(metadata={"status": status, "finding_codes": [
                            f["code"] for f in result.fields.get("findings", [])] if hasattr(result, "fields")
                            else [f.code for f in result.findings]})
                return result
        return wrapper
    return decorate


@contextmanager
def request_trace(request, context, profiles):
    if _client is None:
        yield Observation()
        return
    from langfuse import propagate_attributes
    hashed = hmac.new(_salt, request.subject_key.encode(), hashlib.sha256).hexdigest()
    _subjects[request.subject_key] = hashed
    mode = context.snapshot.context.fields["mode"]
    token = _learning.set(mode == "LEARNING" and not _synthetic)
    try:
        try:
            version = subprocess.check_output(["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL,
                                              text=True).strip()
        except (OSError, subprocess.SubprocessError):
            version = "unknown"
        with propagate_attributes(session_id=context.snapshot.context.id, user_id=hashed,
                tags=[mode, *sorted({p.fields["role"] for p in context.specializations})], version=version, metadata={"request_id": request.request_id,
                "metamodel_version": context.contract.version, "metamodel_fingerprint": context.contract.digest,
                **{"profile." + name: profile for name, profile in profiles.items()}}):
            with observation("learning.request", input=request) as span:
                yield span
    finally:
        _learning.reset(token)


def plan_roles(mode, roles):
    if _client is not None:
        from opentelemetry import trace
        trace.get_current_span().set_attribute("langfuse.trace.tags", [mode, *sorted(set(roles))])


def flush():
    if _client is not None:
        try:
            _client.flush()
        except Exception:
            _logger.warning("Telemetry flush unavailable")
