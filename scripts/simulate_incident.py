"""Simulate bounded, sequential 70% HTTP 500 traffic on the local Flask API."""

import argparse
import math
import time
from http.client import HTTPException
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, ProxyHandler, build_opener


class NoRedirects(HTTPRedirectHandler):
    """Never follow a response to another URL, even if it starts locally."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def bounded_number(name, minimum, maximum):
    """Build an argparse validator that rejects nonfinite or unsafe values."""
    def validate(value):
        try:
            number = float(value)
        except ValueError as error:
            raise argparse.ArgumentTypeError(f"{name} must be a number") from error
        if not math.isfinite(number) or not minimum <= number <= maximum:
            raise argparse.ArgumentTypeError(
                f"{name} must be between {minimum} and {maximum}"
            )
        return number
    return validate


def report(counts, elapsed, final=False):
    """Report HTTP error percentage separately from connection failures."""
    responses = counts["successes"] + counts["http_errors"]
    error_percentage = f'{100 * counts["5xx"] / responses:.1f}%' if responses else "N/A"
    print(
        f'{"Final" if final else "Progress"} [{elapsed:.1f}s]: '
        f'total={counts["total"]}, successes={counts["successes"]}, '
        f'HTTP errors={counts["http_errors"]}, HTTP 500={counts["500"]}, '
        f'network errors={counts["network_errors"]}, '
        f'interrupted requests={counts["interrupted"]}, '
        f'5xx error percentage={error_percentage}',
        flush=True,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--duration", type=bounded_number("duration", 0.01, 1440),
                        default=7.0, help="duration in minutes (default: 7; range: 0.01-1440)")
    parser.add_argument("--rate", type=bounded_number("rate", 0.1, 10),
                        default=1.0, help="maximum requests/second (default: 1; range: 0.1-10)")
    parser.add_argument("--timeout", type=bounded_number("timeout", 0.1, 10),
                        default=5.0, help="HTTP socket timeout in seconds (default: 5; range: 0.1-10)")
    args = parser.parse_args()

    # Fixed IPv4 loopback avoids DNS and exposes no configurable external target.
    # Ignore environment proxies and block all redirects.
    opener = build_opener(ProxyHandler({}), NoRedirects())
    # Seven error and three order requests per complete ten-request cycle.
    # Spread errors throughout the cycle rather than using random selection.
    pattern = ("error", "error", "orders", "error", "error",
               "orders", "error", "error", "orders", "error")
    counts = dict(total=0, successes=0, http_errors=0, network_errors=0,
                  interrupted=0, **{"5xx": 0, "500": 0})
    started = time.monotonic()
    deadline = started + args.duration * 60
    next_request = started
    next_report = started + 30
    interval = 1 / args.rate
    interrupted = False
    in_flight = False

    print(f"Target: http://127.0.0.1:8000 (localhost); duration={args.duration:g} minutes; "
          f"rate at most {args.rate:g} req/s; 70% /api/error, 30% /api/orders.", flush=True)
    try:
        while True:
            now = time.monotonic()
            if now >= next_report:
                report(counts, now - started)
                next_report = now + 30
            if now >= deadline:
                break
            if now < next_request:
                # Wake for reports even at low request rates; Ctrl+C interrupts sleep.
                time.sleep(max(0, min(next_request, next_report, deadline) - now))
                continue

            route = pattern[counts["total"] % len(pattern)]
            counts["total"] += 1
            in_flight = True
            status = None
            request_started = time.monotonic()
            try:
                # Limit the final request's timeout to the remaining run time.
                with opener.open(f"http://127.0.0.1:8000/api/{route}",
                                 timeout=min(args.timeout, deadline - now)) as response:
                    # Only the response status is needed; closing releases the socket.
                    status = response.status
            except HTTPError as error:
                # urllib raises HTTPError for the intentionally generated 500s.
                status = error.code
                error.close()
            except (URLError, OSError, HTTPException):
                counts["network_errors"] += 1

            if status is not None:
                if 200 <= status < 300:
                    counts["successes"] += 1
                else:
                    counts["http_errors"] += 1
                counts["5xx"] += int(500 <= status < 600)
                counts["500"] += int(status == 500)
            in_flight = False
            # Space request starts, accounting for time spent on the request.
            # After slow requests, do not catch up with a burst or overlap requests.
            next_request = max(request_started + interval, time.monotonic())
    except KeyboardInterrupt:
        interrupted = True
        counts["interrupted"] += int(in_flight)
        print("\nStopped safely with Ctrl+C.", flush=True)

    report(counts, time.monotonic() - started, final=True)
    return 130 if interrupted else 0


if __name__ == "__main__":
    raise SystemExit(main())
