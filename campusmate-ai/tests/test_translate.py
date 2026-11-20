import unittest
from unittest.mock import Mock, patch

import app as campusmate


class TranslateEndpointTests(unittest.TestCase):
    def setUp(self):
        self.settings = [
            patch.object(campusmate, "TRANSLATOR_DEMO", False),
            patch.object(campusmate, "TRANSLATOR_EP", "https://translator.example"),
            patch.object(campusmate, "TRANSLATOR_KEY", "test-translator-key"),
            patch.object(campusmate, "TRANSLATOR_REGION", "centralindia")
        ]
        for setting in self.settings:
            setting.start()
            self.addCleanup(setting.stop)
        self.client = campusmate.app.test_client()

    @patch("app.requests.post")
    def test_translation_uses_translator_credentials_and_returns_text(self, post):
        response = Mock()
        response.ok = True
        response.json.return_value = [
            {"translations": [{"text": "मैं तुमसे प्यार करता हूँ"}]}
        ]
        post.return_value = response

        result = self.client.post(
            "/api/translate",
            json={"text": "i love u", "to": "hi"}
        )

        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.get_json()["text"], "मैं तुमसे प्यार करता हूँ")
        kwargs = post.call_args.kwargs
        self.assertEqual(kwargs["params"], {"api-version": "3.0", "to": "hi"})
        self.assertEqual(
            kwargs["headers"]["Ocp-Apim-Subscription-Key"],
            "test-translator-key"
        )
        self.assertEqual(
            kwargs["headers"]["Ocp-Apim-Subscription-Region"],
            "centralindia"
        )
        self.assertEqual(kwargs["timeout"], 20)

    @patch("app.requests.post")
    def test_azure_authentication_errors_are_json_and_do_not_expose_keys(self, post):
        response = Mock()
        response.ok = False
        response.status_code = 401
        post.return_value = response

        result = self.client.post(
            "/api/translate",
            json={"text": "i love u", "to": "hi"}
        )

        self.assertEqual(result.status_code, 502)
        self.assertIn("key and region", result.get_json()["error"])
        self.assertNotIn("test-translator-key", result.get_data(as_text=True))

    @patch("app.requests.post", side_effect=campusmate.requests.Timeout)
    def test_translator_timeout_returns_json_error(self, post):
        result = self.client.post(
            "/api/translate",
            json={"text": "i love u", "to": "hi"}
        )

        self.assertEqual(result.status_code, 504)
        self.assertIn("timed out", result.get_json()["error"])

    @patch("app.requests.post")
    def test_empty_translation_text_is_rejected_as_json(self, post):
        result = self.client.post(
            "/api/translate",
            json={"text": "   ", "to": "hi"}
        )

        self.assertEqual(result.status_code, 400)
        self.assertEqual(result.get_json(), {"error": "Enter text to translate."})
        post.assert_not_called()


if __name__ == "__main__":
    unittest.main()
