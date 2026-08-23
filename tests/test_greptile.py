import json
import unittest
from unittest.mock import patch

from memvet.integrations.greptile import GreptileConfig, GreptileSearchProvider


class FakeResponse:
    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *args) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(
            {
                "sources": [
                    {
                        "repository": "acme/shop",
                        "remote": "github",
                        "branch": "main",
                        "filepath": "src/payments/retry.py",
                        "linestart": 12,
                        "lineend": 28,
                        "summary": "Retry policy is enforced at the payment boundary.",
                    }
                ]
            }
        ).encode()


class GreptileTests(unittest.TestCase):
    def test_search_sends_repository_and_credentials(self) -> None:
        request = None

        def fake_urlopen(request_object, timeout):
            nonlocal request
            request = request_object
            return FakeResponse()

        provider = GreptileSearchProvider(
            GreptileConfig(
                api_key="greptile-key",
                github_token="github-token",
                repository="acme/shop",
                branch="main",
            )
        )
        with patch("memvet.integrations.greptile.urlopen", fake_urlopen):
            references = provider.search("payment retry", limit=3)

        self.assertIsNotNone(request)
        headers = {key.lower(): value for key, value in request.header_items()}
        self.assertEqual(headers["authorization"], "Bearer greptile-key")
        self.assertEqual(headers["x-github-token"], "github-token")
        payload = json.loads(request.data.decode())
        self.assertEqual(payload["query"], "payment retry")
        self.assertEqual(payload["repositories"][0]["repository"], "acme/shop")
        self.assertEqual(references[0].path, "src/payments/retry.py")
        self.assertEqual(references[0].line_start, 12)
        self.assertEqual(references[0].line_end, 28)


if __name__ == "__main__":
    unittest.main()
