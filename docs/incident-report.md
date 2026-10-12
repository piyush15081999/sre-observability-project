# Incident report: FlaskHighErrorRate simulation

## Incident summary

| Field | Detail |
| --- | --- |
| Environment | Local Flask, Prometheus, and Grafana observability project |
| Classification | Intentional incident simulation |
| Service / Prometheus job | Flask API / `flask-api` |
| Alert | `FlaskHighErrorRate` |
| Configured severity | `warning` |
| Incident date and timestamps | Unknown |
| Incident duration | Unknown |
| Final observed alert state | INACTIVE, as reported by the operator |

The operator confirmed a successful simulation in which the observed peak error rate was approximately 70%. The alert transitioned **INACTIVE → PENDING → FIRING → INACTIVE**. Recovery followed stopping the simulated failures and sending healthy API requests.

This report records the operator's verified observations and the current repository configuration. Raw incident logs, timestamped screenshots, query exports, and exact request counts were not supplied. No log excerpts or timestamps are inferred.

## Detection and impact

**Observed:** `FlaskHighErrorRate` reached FIRING, the peak error rate was approximately 70%, and the alert subsequently returned to INACTIVE. The source panel/query and sampling time for the peak measurement are unknown.

**Verified configuration:** the rule requires a five-minute HTTP 5xx ratio strictly greater than 5%, at least 20 estimated eligible requests in that window, and positive request activity over the last minute. These conditions must persist across evaluations for five continuous minutes. Evaluations and scrapes are configured every 15 seconds. Eligible traffic excludes `/health` and `/metrics` and aggregates all methods and other endpoints.

**Impact:** simulated requests deliberately received failure responses from the local API. Exact failure counts, total requests, affected users, external customer impact, and incident-specific latency are unknown. This exercise does not establish a production outage or a production SLO breach.

**Expected, not an additional observation:** the dedicated simulator sends seven requests to `/api/error` and three to `/api/orders` per complete ten-request cycle. In isolation, with expected responses, this produces 70% HTTP 500 responses. Other traffic, scrape boundaries, and incomplete cycles can change the measured ratio. Its defaults of seven minutes and one request/second are configuration values; they are not proof of the actual incident duration or rate.

## Timeline

Events below are in reported sequence. All timestamps and elapsed intervals are unknown.

| Timestamp | Event | Evidence / qualification |
| --- | --- | --- |
| Unknown | Alert initially INACTIVE | Operator-confirmed state sequence |
| Unknown | Intentional failure simulation active | Operator-confirmed simulation; exact invocation unknown |
| Unknown | Alert became PENDING | Operator-confirmed state sequence |
| Unknown | Peak error rate approximately 70% | Operator-confirmed value; position relative to FIRING unknown |
| Unknown | Alert became FIRING | Operator-confirmed state sequence |
| Unknown | Simulated failures stopped; healthy API traffic sent | Operator-confirmed recovery actions; exact commands/counts unknown |
| Unknown | Alert returned to INACTIVE | Operator-confirmed recovery outcome |

The configured five-minute hold explains the expected Pending-to-Firing behavior. It does not supply missing timestamps or establish exact detection or recovery times.

## Root cause

The root cause was **intentional simulated failures**, not a verified application defect. The registered `/api/error` handler deliberately returns HTTP 500 with a JSON error response; `/api/orders` returns HTTP 200 with sample orders. These responses pass through the existing application-wide instrumentation.

The alert correctly detected the reported simulated high-error condition. No database failure, resource exhaustion, dependency outage, unexpected exception, or deployment regression was evidenced for this incident.

## Investigation: PromQL and Docker logs

The queries and commands below are reproducible investigation steps, not a claim that their outputs were captured during the incident. Run PromQL in local Prometheus or Grafana Explore. For historical investigation, select the incident window once timestamps become available; live queries do not reconstruct an unknown past window.

### Error ratio and traffic guards

```promql
sum by (job) (rate(flask_http_requests_total{job="flask-api",endpoint!="/health",endpoint!="/metrics",status=~"5.."}[5m]))
/
sum by (job) (rate(flask_http_requests_total{job="flask-api",endpoint!="/health",endpoint!="/metrics"}[5m]))
```

This is the five-minute 5xx ratio, between 0 and 1; multiply by 100 for percent. `rate` handles counter resets before aggregation. A missing 5xx series can produce no result; that is not evidence of an outage. For a zero-filled display with positive traffic, use the existing dashboard's error percentage panel.

```promql
sum by (job) (increase(flask_http_requests_total{job="flask-api",endpoint!="/health",endpoint!="/metrics"}[5m]))
```

This estimates the eligible request count over five minutes. The alert requires `>= 20`; `increase` extrapolation means counts can be fractional.

```promql
sum by (job) (rate(flask_http_requests_total{job="flask-api",endpoint!="/health",endpoint!="/metrics"}[1m]))
```

The alert also requires this recent request rate to be positive. Alert inactivity alone cannot prove recovery: insufficient traffic or missing data can deactivate the rule.

### Affected routes and alert states

```promql
sum by (endpoint, method, status) (rate(flask_http_requests_total{job="flask-api",endpoint!="/health",endpoint!="/metrics",status=~"5.."}[5m]))
```

This identifies which endpoint, method, and 5xx status series contribute errors, in requests/second. Actual incident output was not supplied.

```promql
ALERTS{alertname="FlaskHighErrorRate",alertstate=~"pending|firing"}
```

Active states have value 1. INACTIVE has no active series. The operator reported the full lifecycle; no historical series export accompanies this report.

In Windows PowerShell, from the project folder:

```powershell
docker compose ps
docker compose logs --since=10m --tail=200 api
docker compose logs --since=10m --tail=100 prometheus
```

Choose a log window that actually covers the incident. Gunicorn is configured to emit access and error logs, but no incident log evidence is included here. The deliberate handler returns a controlled 500, so a traceback is not required for that response.

## Mitigation and recovery

**Observed actions:** simulated failures were stopped and healthy API requests were sent. **Observed outcome:** the alert returned to INACTIVE.

**Expected mechanism:** stopping deliberate failures prevents additional simulated 5xx responses. Healthy eligible requests lower the five-minute error ratio, while older failures age out. The alert resolves on the next evaluation once any required condition becomes false; the recent-traffic guard can also deactivate it if requests stop. The exact resolving condition and recovery interval are unknown for this incident.

No restart, rebuild, rollback, alert threshold change, or metric deletion was reported as part of recovery. Previously recorded failures remain in the rolling 30-day SLO calculation until they age out; alert resolution does not reset the error budget.

## Verification steps

Use the [incident runbook](incident-runbook.md) for the detailed procedure. These checks are recommended acceptance criteria, not additional observed incident results:

1. Confirm `/health` and `/api/orders` return HTTP 200.
2. Confirm `up{job="flask-api"}` is 1 and the alert rule health is `ok`.
3. Send eligible healthy traffic, verify a positive recent request rate, and verify the five-minute 5xx ratio is at or below 5%.
4. Confirm `FlaskHighErrorRate` is INACTIVE in Prometheus and no active `ALERTS` series remains.
5. Inspect the SRE dashboard and retain the 30-day error budget evidence rather than resetting it.

Only the final INACTIVE state and reported recovery actions are confirmed for this incident; the other checks have no incident-specific results supplied.

## Lessons learned

- The reported state transitions demonstrate detection, sustained-condition escalation, and subsequent deactivation for this simulation.
- `/health` alone is insufficient to establish user API reliability; the deliberate error endpoint can fail while liveness remains healthy.
- The five-minute observation window and five-minute hold are distinct. FIRING does not mean a five-minute incident duration.
- Healthy traffic and scrape verification distinguish recovery from silence or monitoring failure.
- Missing timestamps and saved telemetry limit precise analysis of detection delay, impact, and recovery time.

## Prevention and improvements

The following are proposals, not completed changes or assigned commitments. Owners and target dates are unassigned.

| Proposed improvement | Purpose |
| --- | --- |
| Capture timestamped state transitions, query exports, and simulator totals on the next exercise | Establish detection/recovery timing and request impact |
| Record the exact simulation command and distinguish test traffic in evidence | Make results reproducible without confusing them with real incidents |
| Keep deliberate failure traffic confined to the local exercise; gate demo endpoints before any nonlocal deployment | Prevent accidental intentional failures outside the exercise |
| Maintain synthetic rule tests for timing, traffic guards, and exclusions | Reduce regressions in alert behavior |
| Consider a separate scrape-failure or external availability check | Cover failures not visible to Flask request counters |
| Evaluate SLO burn-rate alerting separately from the current high-error rule | Align future detection with long-term error-budget risk |

The current alert threshold, API endpoints, metrics, and containers are unchanged by this documentation. The operator subsequently confirmed Alertmanager webhook firing and resolved delivery. Exact notification timestamps and raw delivery logs were not supplied; this confirmation does not fill gaps in the original incident timeline.
