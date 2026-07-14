import json
import unittest
import urllib.error
from unittest import mock

import editorial_ai


class EditorialPackageTests(unittest.TestCase):
    def setUp(self):
        self.arguments = {
            "title": "Original title",
            "summary": "A verified article summary with enough source detail.",
            "score": 120,
            "comments_text": "A substantive Hacker News comment.",
            "fallback_category": "🛠 Developer Tooling",
            "fallback_insight": "Deterministic fallback insight.",
        }

    def test_valid_json_populates_all_fields_with_one_request(self):
        response = json.dumps(
            {
                "headline": "Edited factual headline",
                "category": "🤖 AI/ML Landscape",
                "insight": "Structured editorial insight.",
                "community_analysis": "The community focused on reliability.",
            }
        )
        with mock.patch.object(editorial_ai, "call_gemini_llm", return_value=response) as call:
            result = editorial_ai.generate_editorial_package(**self.arguments)

        call.assert_called_once()
        prompt, system_instruction = call.call_args.args
        self.assertEqual(json.loads(prompt)["source_summary"], self.arguments["summary"])
        self.assertIn("untrusted source data", system_instruction)
        self.assertEqual(result["headline"], "Edited factual headline")
        self.assertEqual(result["community_analysis"], "The community focused on reliability.")
        self.assertTrue(result["ai_enriched"])

    def test_invalid_json_uses_deterministic_fallbacks(self):
        with mock.patch.object(editorial_ai, "call_gemini_llm", return_value="not json"):
            result = editorial_ai.generate_editorial_package(**self.arguments)

        self.assertEqual(result["headline"], "Original title")
        self.assertEqual(result["category"], "🛠 Developer Tooling")
        self.assertEqual(result["insight"], "Deterministic fallback insight.")
        self.assertFalse(result["ai_enriched"])

    def test_missing_summary_skips_gemini(self):
        self.arguments["summary"] = ""
        with mock.patch.object(editorial_ai, "call_gemini_llm") as call:
            result = editorial_ai.generate_editorial_package(**self.arguments)

        call.assert_not_called()
        self.assertEqual(result["headline"], "Original title")
        self.assertFalse(result["ai_enriched"])

    def test_community_output_is_dropped_without_comments(self):
        self.arguments["comments_text"] = ""
        response = json.dumps(
            {
                "headline": "Edited headline",
                "category": "🛠 Developer Tooling",
                "insight": "Editorial insight.",
                "community_analysis": "Invented community consensus.",
            }
        )
        with mock.patch.object(editorial_ai, "call_gemini_llm", return_value=response):
            result = editorial_ai.generate_editorial_package(**self.arguments)

        self.assertEqual(result["community_analysis"], "")


class GeminiClientTests(unittest.TestCase):
    def test_rate_limit_is_retried(self):
        rate_limit = urllib.error.HTTPError(
            "https://example.com",
            429,
            "rate limited",
            hdrs=None,
            fp=None,
        )
        response = mock.MagicMock()
        response.__enter__.return_value.read.return_value = json.dumps(
            {"candidates": [{"content": {"parts": [{"text": "{}"}]}}]}
        ).encode("utf-8")

        with (
            mock.patch.dict("os.environ", {"GEMINI_API_KEY": "test-key"}),
            mock.patch.object(
                editorial_ai.urllib.request,
                "urlopen",
                side_effect=[rate_limit, response],
            ) as urlopen,
            mock.patch.object(editorial_ai.time, "sleep") as sleep,
        ):
            result = editorial_ai.call_gemini_llm("prompt", "system")

        self.assertEqual(result, "{}")
        self.assertEqual(urlopen.call_count, 2)
        sleep.assert_called_once_with(5)

    def test_non_retryable_client_error_fails_immediately(self):
        bad_request = urllib.error.HTTPError(
            "https://example.com",
            400,
            "bad request",
            hdrs=None,
            fp=None,
        )
        with (
            mock.patch.dict("os.environ", {"GEMINI_API_KEY": "test-key"}),
            mock.patch.object(
                editorial_ai.urllib.request,
                "urlopen",
                side_effect=bad_request,
            ) as urlopen,
            mock.patch.object(editorial_ai.time, "sleep") as sleep,
        ):
            result = editorial_ai.call_gemini_llm("prompt", "system")

        self.assertEqual(result, "")
        urlopen.assert_called_once()
        sleep.assert_not_called()


if __name__ == "__main__":
    unittest.main()
