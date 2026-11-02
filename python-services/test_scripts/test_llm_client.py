import unittest
from unittest.mock import patch

from parser import llm_client


class LLMClientRoutingTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        env = patch.dict("os.environ", {
            "GROQ_API_KEY": "test", "GEMINI_API_KEY": "test", "NVIDIA_API_KEY": "",
            "GROQ_MODEL": "primary", "GROQ_FALLBACK_MODEL": "backup", "GEMINI_MODEL": "gemini-primary",
            "GEMINI_FALLBACK_MODEL": "", "LLM_CROSS_PROVIDER_FALLBACK": "true",
        })
        env.start()
        self.addCleanup(env.stop)
        llm_client.set_provider("groq")

    async def _complete(self, responses: dict):
        original = llm_client._deployment

        def mocked(group, provider, model):
            deployment = original(group, provider, model)
            deployment["litellm_params"]["mock_response"] = responses[group]
            return deployment

        with patch.object(llm_client, "_deployment", mocked):
            llm_client.set_provider("groq")
            return await llm_client.budgeted_completion([{"role": "user", "content": "hi"}])

    def _unavailable(self):
        # LiteLLM copies deployment params, so a plain exception stands in for a provider 503.
        return Exception("503 Service Unavailable: model overloaded")

    def test_routing_order_prefers_chosen_provider(self):
        groups = [group for group, _, _ in llm_client._model_groups(llm_client.get_provider())]
        self.assertEqual(groups, ["groq", "groq-fallback", "google", "google-fallback"])

    def test_cross_provider_fallback_can_be_disabled(self):
        with patch.dict("os.environ", {"LLM_CROSS_PROVIDER_FALLBACK": "false"}):
            groups = [group for group, _, _ in llm_client._model_groups(llm_client.get_provider())]
        self.assertEqual(groups, ["groq", "groq-fallback"])

    async def test_primary_answers(self):
        response = await self._complete({
            "groq": "from groq", "groq-fallback": "from backup",
            "google": "from gemini", "google-fallback": "from gemini lite",
        })
        self.assertEqual(response.choices[0].message.content, "from groq")

    async def test_unavailable_provider_falls_back(self):
        response = await self._complete({
            "groq": self._unavailable(), "groq-fallback": self._unavailable(),
            "google": "from gemini", "google-fallback": "from gemini lite",
        })
        self.assertEqual(response.choices[0].message.content, "from gemini")

    async def test_all_providers_failing_raises_clear_error(self):
        with self.assertRaisesRegex(RuntimeError, "All configured LLM providers failed"):
            await self._complete({group: self._unavailable() for group in
                                  ("groq", "groq-fallback", "google", "google-fallback")})


if __name__ == "__main__":
    unittest.main()
