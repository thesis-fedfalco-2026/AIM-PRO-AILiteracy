"""Recover transient OpenRouter SSE errors that bypass the SDK's HTTP retries."""

import logging
import time

from crewai.llms.providers.openai.completion import OpenAICompletion
from openai import APIError


class OpenRouterCompletion(OpenAICompletion):
    def _handle_streaming_completion(self, *args, **kwargs):
        for attempt in range(3):
            try:
                return super()._handle_streaming_completion(*args, **kwargs)
            except APIError as error:
                # HTTP status errors already have SDK retries. Only SSE errors
                # arrive as plain APIError, with the status in the JSON body.
                code = error.body.get("code") if isinstance(error.body, dict) else None
                if type(error) is not APIError or code not in (408, 429, 500, 502, 503, 504):
                    raise
                if attempt == 2:
                    logging.getLogger("agent_system").error(
                        "OpenRouter stream failed after 3 attempts (code=%s)", code)
                    raise
                delay = 2 ** (attempt + 1)
                logging.getLogger("agent_system").warning(
                    "OpenRouter stream interrupted (code=%s); retry %s/2 in %ss",
                    code, attempt + 1, delay)
                time.sleep(delay)
