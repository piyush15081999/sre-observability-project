"""Exercise the local webhook protocol and logs without third-party packages."""

import json
import threading
import unittest
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import ProxyHandler, Request, build_opener

from monitoring.webhook_receiver.server import WebhookHandler


class WebhookTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), WebhookHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = f"http://127.0.0.1:{cls.server.server_port}"
        cls.opener = build_opener(ProxyHandler({}))

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def test_health(self):
        with self.opener.open(self.url + "/health", timeout=3) as response:
            self.assertEqual(response.status, 200)

    def test_firing_and_resolved_logs(self):
        for status in ("firing", "resolved"):
            with self.subTest(status=status):
                payload = {"status": status, "alerts": [{"status": status,
                           "labels": {"alertname": "FlaskHighErrorRate", "job": "flask-api",
                                      "password": "do-not-log"},
                           "annotations": {"secret": "do-not-log"}}]}
                request = Request(self.url + "/webhook", data=json.dumps(payload).encode(),
                                  headers={"Content-Type": "application/json"})
                with self.assertLogs("alert-webhook", level="INFO") as captured:
                    with self.opener.open(request, timeout=3) as response:
                        self.assertEqual(response.status, 200)
                        self.assertEqual(json.load(response), {"received": 1})
                self.assertIn(status, captured.output[0])
                self.assertIn("FlaskHighErrorRate", captured.output[0])
                self.assertNotIn("do-not-log", captured.output[0])

    def test_malformed_payload(self):
        for body in (b"not json", b"[]", b'{"status":"firing","alerts":[]}'):
            with self.subTest(body=body):
                request = Request(self.url + "/webhook", data=body)
                with self.assertRaises(HTTPError) as caught:
                    self.opener.open(request, timeout=3)
                self.assertEqual(caught.exception.code, 400)
                caught.exception.close()


if __name__ == "__main__":
    unittest.main()
