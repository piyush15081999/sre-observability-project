"""Opt-in endpoints for exercising error and latency monitoring locally."""

from time import sleep

from flask import Blueprint, jsonify

traffic_api = Blueprint("traffic_api", __name__, url_prefix="/test")


@traffic_api.get("/error")
def deliberate_error():
    # Return a controlled 500 so the normal request instrumentation records it.
    return jsonify(error="Deliberate traffic-test failure"), 500


@traffic_api.get("/slow")
def deliberate_delay():
    # Keep the delay fixed and bounded; callers cannot request arbitrary sleeps.
    sleep(1.0)
    return jsonify(status="ok", delay_seconds=1.0), 200
