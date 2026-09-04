import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from main import load_llm_options


class ModelConfigTest(unittest.TestCase):
    def test_backend_comes_from_properties_and_key_from_environment(self):
        source = Path("model.properties").read_text()
        expected = {
            "vllm": ("hosted_vllm", "local-model"),
            "openai": ("openai", "gpt-4.1-mini"),
            "anthropic": ("anthropic", "claude-sonnet-4-6"),
        }

        for backend, (provider, model) in expected.items():
            with self.subTest(backend=backend), tempfile.NamedTemporaryFile(
                mode="w", suffix=".properties"
            ) as properties:
                properties.write(source.replace("backend = vllm", f"backend = {backend}", 1))
                properties.flush()
                with patch.dict(
                    os.environ,
                    {f"{backend.upper()}_API_KEY": "test", "LLM_PROVIDER": "ignored"},
                    clear=True,
                ):
                    options = load_llm_options(properties.name)
                self.assertEqual(options["provider"], provider)
                self.assertEqual(options["model"], model)
                if backend == "vllm":
                    self.assertEqual(options["base_url"], "http://127.0.0.1:8000/v1")

        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(ValueError, "Set VLLM_API_KEY"):
                load_llm_options()


if __name__ == "__main__":
    unittest.main()
