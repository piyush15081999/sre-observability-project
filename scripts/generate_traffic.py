"""Generate bounded, sequential traffic against the local Flask API.

Uses only Python's standard library; no package installation is required.
"""

import argparse
import math
import statistics
import time
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, ProxyHandler, build_opener


class NoRedirects(HTTPRedirectHandler):
    """Prevent a local response from redirecting requests to another host."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def bounded_count(value):
    count = int(value)
    if not 1 <= count <= 10000:
        raise argparse.ArgumentTypeError("count must be between 1 and 10000")
    return count


def bounded_delay(value):
    delay = float(value)
    if not math.isfinite(delay) or not 0.1 <= delay <= 60:
        raise argparse.ArgumentTypeError("delay must be between 0.1 and 60 seconds")
    return delay


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=bounded_count, default=30,
                        help="total requests across all endpoints (1-10000; default: 30)")
    parser.add_argument("--delay", type=bounded_delay, default=0.5,
                        help="pause between requests in seconds (0.1-60; default: 0.5)")
    args = parser.parse_args()

    # Use IPv4 loopback directly, bypass proxies, and prohibit redirects.
    # No user-supplied host or URL can send traffic outside this computer.
    opener = build_opener(ProxyHandler({}), NoRedirects())
    paths = ("/api/orders", "/api/error", "/api/slow")
    latencies = []
    successes = failures = expected_errors = unexpected = 0
    started = time.perf_counter()
    interrupted = False

    print("Target: http://127.0.0.1:8000 (localhost)")
    try:
        for index in range(args.count):
            # Each three-request cycle exercises success, HTTP 500, and latency.
            path = paths[index % len(paths)]
            request_started = time.perf_counter()
            status = None
            detail = ""
            try:
                with opener.open(f"http://127.0.0.1:8000{path}", timeout=5) as response:
                    response.read()
                    status = response.status
            except HTTPError as error:
                # HTTP errors are completed responses, including deliberate 500s.
                status = error.code
                error.close()
            except (URLError, TimeoutError, OSError) as error:
                detail = str(error)

            elapsed = time.perf_counter() - request_started
            latencies.append(elapsed)
            if status is not None and 200 <= status < 300:
                successes += 1
            else:
                failures += 1
            expected_status = 500 if path == "/api/error" else 200
            if path == "/api/error" and status == 500:
                expected_errors += 1
            if status != expected_status:
                unexpected += 1
            print(f"{index + 1}/{args.count} {path}: "
                  f"{status if status is not None else 'network error'} "
                  f"{elapsed * 1000:.1f} ms {detail}")

            # Sequential requests plus a minimum pause bound traffic to 10 req/s.
            # Slow requests reduce the rate further; there is no catch-up burst.
            if index + 1 < args.count:
                time.sleep(args.delay)
    except KeyboardInterrupt:
        interrupted = True
        print("\nInterrupted; reporting completed requests.")

    print(f"\nTotal requests: {len(latencies)}")
    print(f"Successes (HTTP 2xx): {successes}")
    print(f"Failures (HTTP errors or network errors): {failures}")
    print(f"Deliberate HTTP 500 responses: {expected_errors}")
    print(f"Unexpected outcomes: {unexpected}")
    if latencies:
        print(f"Latency ms (min/average/max): {min(latencies) * 1000:.1f} / "
              f"{statistics.mean(latencies) * 1000:.1f} / {max(latencies) * 1000:.1f}")
    print(f"Run duration: {time.perf_counter() - started:.2f} seconds")
    # Expected 500 responses do not signal script failure; unexpected ones do.
    return 130 if interrupted else (1 if unexpected else 0)


if __name__ == "__main__":
    raise SystemExit(main())
