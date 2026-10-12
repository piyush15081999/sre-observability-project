"""Flask application factory and HTTP request instrumentation."""

import os
from time import perf_counter

from flask import Flask, g, request

from app.metrics import REQUEST_COUNT, REQUEST_DURATION
from app.routes import api


def create_app():
    """Build the API and register its routes and monitoring hooks."""
    app = Flask(__name__)
    app.register_blueprint(api)

    # Test routes are absent unless explicitly enabled for local traffic testing.
    if os.environ.get("ENABLE_TRAFFIC_TEST_ENDPOINTS", "false").lower() == "true":
        from app.traffic_routes import traffic_api

        app.register_blueprint(traffic_api)

    @app.before_request
    def start_timer():
        # A monotonic clock measures elapsed time without clock-adjustment errors.
        g.request_started = perf_counter()

    @app.after_request
    def record_metrics(response):
        # Exclude scrapes so monitoring does not inflate API traffic statistics.
        if request.path != "/metrics":
            # Use route templates instead of raw URLs to limit label cardinality.
            endpoint = request.url_rule.rule if request.url_rule else "unmatched"
            REQUEST_COUNT.labels(
                method=request.method,
                endpoint=endpoint,
                status=str(response.status_code),
            ).inc()
            REQUEST_DURATION.labels(
                method=request.method, endpoint=endpoint
            ).observe(perf_counter() - g.request_started)
        return response

    return app
