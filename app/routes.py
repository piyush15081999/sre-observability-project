"""Health and Prometheus exposition endpoints."""

from flask import Blueprint, Response, jsonify
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from app.traffic_routes import deliberate_delay, deliberate_error

api = Blueprint("api", __name__)

# Register the monitoring demo endpoints regardless of the optional /test routes.
# Reuse the same handlers to keep error and delay behavior consistent.
api.add_url_rule("/api/error", view_func=deliberate_error, methods=["GET"])
api.add_url_rule("/api/slow", view_func=deliberate_delay, methods=["GET"])


@api.get("/api/orders")
def orders():
    # Static sample data keeps this starter independent of a database.
    return jsonify(orders=[
        {"id": 1, "item": "Notebook", "quantity": 2},
        {"id": 2, "item": "Pen", "quantity": 5},
    ]), 200


@api.get("/health")
def health():
    # This liveness check confirms the API can respond; it checks no dependencies.
    return jsonify(status="ok"), 200


@api.get("/metrics")
def metrics():
    # Export application collectors and the client's default process metrics.
    return Response(generate_latest(), content_type=CONTENT_TYPE_LATEST)
