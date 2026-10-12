"""Prometheus collectors shared by the API routes and request hooks."""

from prometheus_client import Counter, Histogram

# Counters only increase; Prometheus can calculate request rates from them.
REQUEST_COUNT = Counter(
    "flask_http_requests_total",
    "Total API requests by method, route, and response status.",
    ["method", "endpoint", "status"],
)

# Histograms support latency percentiles calculated across time in Prometheus.
REQUEST_DURATION = Histogram(
    "flask_http_request_duration_seconds",
    "API request duration in seconds.",
    ["method", "endpoint"],
)
