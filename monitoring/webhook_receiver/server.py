"""Local Alertmanager webhook logger using only the Python standard library."""

import json
import logging
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

LOGGER = logging.getLogger("alert-webhook")
MAX_BODY_BYTES = 1024 * 1024


class WebhookHandler(BaseHTTPRequestHandler):
    """Acknowledge valid notifications only after writing the log entry."""

    def setup(self):
        super().setup()
        # Bound stalled connections and request-body reads.
        self.connection.settimeout(5)

    def respond(self, status, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/health":
            self.respond(200, {"status": "ok"})
        else:
            self.respond(404, {"error": "Not found"})

    def do_POST(self):
        if self.path != "/webhook":
            self.respond(404, {"error": "Not found"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= MAX_BODY_BYTES:
                self.respond(413, {"error": "Body must be between 1 byte and 1 MiB"})
                return
            notification = json.loads(self.rfile.read(length))
            if not isinstance(notification, dict):
                raise ValueError("Expected JSON object")
            alerts = notification.get("alerts")
            if notification.get("status") not in ("firing", "resolved") or not isinstance(alerts, list) or not alerts:
                raise ValueError("Expected status and nonempty alerts list")
            events = []
            for alert in alerts:
                if not isinstance(alert, dict) or alert.get("status") not in ("firing", "resolved"):
                    raise ValueError("Invalid alert")
                labels = alert.get("labels", {})
                if not isinstance(labels, dict):
                    raise ValueError("Invalid labels")
                # Whitelist operational fields; never log headers, credentials,
                # arbitrary annotations, or the unfiltered incoming body.
                events.append({
                    "status": alert["status"],
                    "labels": {key: labels[key] for key in
                               ("alertname", "job", "service", "severity") if key in labels},
                    "startsAt": alert.get("startsAt"),
                    "endsAt": alert.get("endsAt"),
                })
        except (ValueError, UnicodeError):
            self.respond(400, {"error": "Invalid notification JSON"})
            return
        except OSError:
            self.respond(408, {"error": "Request read timed out or failed"})
            return

        # JSON escapes embedded newlines, preserving one event per log line.
        LOGGER.info("notification %s", json.dumps({
            "status": notification["status"],
            "alert_count": len(events),
            "alerts": events,
        }, ensure_ascii=True))
        self.respond(200, {"received": len(events)})

    def log_message(self, format, *args):
        # Suppress request/access logs, including routine health-check noise.
        pass


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    # Listening on the container interface is required for Docker service DNS.
    # Compose publishes no host port for this receiver.
    server = ThreadingHTTPServer(("0.0.0.0", 8080), WebhookHandler)
    LOGGER.info("Local notification receiver listening on container port 8080")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
