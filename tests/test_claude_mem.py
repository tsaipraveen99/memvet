import json
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from memvet.integrations.claude_mem import ClaudeMemConfig, ClaudeMemSearchProvider


class FakeResponse:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *args) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode()


class ClaudeMemTests(unittest.TestCase):
    def test_search_maps_worker_results_and_sends_api_key(self) -> None:
        request = None

        def fake_urlopen(request_object, timeout):
            nonlocal request
            request = request_object
            return FakeResponse(
                {
                    "results": [
                        {
                            "id": 42,
                            "title": "Keep retries at the boundary",
                            "narrative": "The client retries once; the worker remains idempotent.",
                            "score": 0.91,
                        }
                    ]
                }
            )

        provider = ClaudeMemSearchProvider(
            ClaudeMemConfig(
                base_url="http://127.0.0.1:37700",
                api_key="test-key",
                search_path="/api/search",
            )
        )
        with patch("memvet.integrations.claude_mem.urlopen", fake_urlopen):
            hits = provider.search("retry policy", limit=3)

        self.assertIsNotNone(request)
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].id, "42")
        self.assertEqual(hits[0].source, "claude-mem:42")
        self.assertEqual(hits[0].score, 0.91)
        self.assertEqual(parse_qs(urlparse(request.full_url).query)["query"], ["retry policy"])
        self.assertEqual(request.get_header("X-api-key"), "test-key")


if __name__ == "__main__":
    unittest.main()
