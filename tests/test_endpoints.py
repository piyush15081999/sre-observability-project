"""Verify the actual WSGI app and exported metrics without extra test packages."""

import time
import unittest

from prometheus_client import REGISTRY

from wsgi import app


class EndpointTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def sample(self, name, labels):
        # Read public registry samples; use deltas because collectors are shared.
        return REGISTRY.get_sample_value(name, labels) or 0.0

    def test_routes_and_request_metrics(self):
        for path, status in (("/health", 200), ("/api/orders", 200),
                             ("/api/error", 500), ("/api/slow", 200)):
            with self.subTest(path=path):
                counter_labels = {"method": "GET", "endpoint": path, "status": str(status)}
                duration_labels = {"method": "GET", "endpoint": path}
                count_before = self.sample("flask_http_requests_total", counter_labels)
                observations_before = self.sample("flask_http_request_duration_seconds_count", duration_labels)
                duration_before = self.sample("flask_http_request_duration_seconds_sum", duration_labels)
                started = time.perf_counter()
                response = self.client.get(path)
                elapsed = time.perf_counter() - started
                self.assertEqual(response.status_code, status)
                self.assertTrue(response.is_json)
                self.assertEqual(self.sample("flask_http_requests_total", counter_labels) - count_before, 1)
                self.assertEqual(self.sample("flask_http_request_duration_seconds_count", duration_labels) - observations_before, 1)
                if path == "/health":
                    self.assertEqual(response.json, {"status": "ok"})
                elif path == "/api/orders":
                    self.assertTrue(response.json["orders"])
                    self.assertIn("id", response.json["orders"][0])
                elif path == "/api/error":
                    self.assertIn("error", response.json)
                elif path == "/api/slow":
                    self.assertEqual(response.json["delay_seconds"], 1.0)
                    self.assertGreaterEqual(elapsed, 1.0)
                    self.assertGreaterEqual(self.sample("flask_http_request_duration_seconds_sum", duration_labels) - duration_before, 1.0)

    def test_metrics_exposition_and_scrape_exclusion(self):
        # Generate both collectors, then verify the actual exposition endpoint.
        self.client.get("/api/error")
        before = sum(sample.value for metric in REGISTRY.collect()
                     for sample in metric.samples if sample.name == "flask_http_requests_total")
        response = self.client.get("/metrics")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.content_type.startswith("text/plain"))
        body = response.get_data(as_text=True)
        self.assertIn('flask_http_requests_total{endpoint="/api/error",method="GET",status="500"}', body)
        self.assertIn("flask_http_request_duration_seconds_bucket", body)
        after = sum(sample.value for metric in REGISTRY.collect()
                    for sample in metric.samples if sample.name == "flask_http_requests_total")
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
