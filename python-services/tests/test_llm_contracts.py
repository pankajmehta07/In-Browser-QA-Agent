import json
import os
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, MagicMock, patch

from parser.natural_language import respond_to_instruction, resolve_button_with_llm


class LlmContracts(IsolatedAsyncioTestCase):
    def client(self, content):
        provider = MagicMock()
        client = provider.return_value.__aenter__.return_value
        client.chat.completions.create = AsyncMock(return_value=SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=content))]))
        return provider, client

    async def test_workflow_response_is_decoded_without_network(self):
        payload = {"kind": "test", "answer": None, "steps": [{"action": "click", "target": "Login"}]}
        provider, client = self.client(json.dumps(payload))
        snapshot = SimpleNamespace(url="http://127.0.0.1:5173/", nodes=[])
        with patch.dict(os.environ, {"GROQ_API_KEY": "test-only-not-a-real-key"}), \
             patch("parser.natural_language.AsyncGroq", provider):
            result = await respond_to_instruction("Click Login", snapshot, "Demo", "Login")
        self.assertEqual(result.kind, "test")
        self.assertEqual(json.loads(result.steps_json), payload["steps"])
        client.chat.completions.create.assert_awaited_once()

    async def test_malformed_provider_output_is_reported(self):
        provider, _ = self.client("not-json")
        with patch.dict(os.environ, {"GROQ_API_KEY": "test-only-not-a-real-key"}), \
             patch("parser.natural_language.AsyncGroq", provider):
            with self.assertRaisesRegex(ValueError, "invalid JSON"):
                await respond_to_instruction("Click Login", SimpleNamespace(url="http://localhost/", nodes=[]), "Demo", "")

    async def test_hallucinated_button_is_not_accepted(self):
        provider, _ = self.client("Invented Button")
        with patch.dict(os.environ, {"GROQ_API_KEY": "test-only-not-a-real-key"}), \
             patch("parser.natural_language.AsyncGroq", provider):
            result = await resolve_button_with_llm("Save", ["Create Project", "Cancel"])
        self.assertIsNone(result)

    async def test_missing_key_does_not_construct_a_provider(self):
        with patch.dict(os.environ, {"GROQ_API_KEY": ""}), \
             patch("parser.natural_language.AsyncGroq") as provider:
            with self.assertRaisesRegex(RuntimeError, "GROQ_API_KEY"):
                await resolve_button_with_llm("Save", ["Save"])
        provider.assert_not_called()
