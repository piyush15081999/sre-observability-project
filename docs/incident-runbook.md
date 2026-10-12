# Runbook: FlaskHighErrorRate

## Purpose and incident summary

Respond to sustained HTTP 5xx failures in the local Flask observability project. A completed exercise was reported with approximately 70% peak errors and **INACTIVE → PENDING → FIRING → INACTIVE**, followed by stopping simulated failures and sending healthy requests. Exact timestamps, duration, counts, and log evidence are unknown. See the [incident report](incident-report.md).

This runbook is an operational procedure. Its expected outcomes are not additional observations from that exercise.

## Detection and impact

| Item | Current configuration |
| --- | --- |
| Alert | `FlaskHighErrorRate` |
| Severity | `warning` |
| Service / job | `flask-api` |
| Threshold | Five-minute HTTP 5xx ratio strictly above 5% |
| Traffic floor | At least 20 estimated eligible requests in five minutes |
| Recent activity | Positive eligible request rate over the last minute |
| Hold | All conditions true for five continuous minutes |
| Evaluation | Every 15 seconds |
| Exclusions | `/health` and `/metrics` |
| Availability SLO | Non-5xx eligible requests / all eligible requests, at least 99.9% over rolling 30 days |

4xx responses count as available under this SLI. Request metrics cannot measure requests that never reach Flask. The histogram has `endpoint` and `method` labels; `status` is on the request counter. Preserve the existing definitions when investigating.

Local interfaces:

- API: http://localhost:8000
- Prometheus alerts: http://localhost:9090/alerts
- Prometheus rules: http://localhost:9090/rules
- Grafana: http://localhost:3000/d/sre-flask-service-overview/sre-flask-service-overview
- Alertmanager: http://localhost:9093

**Pending** means the conditions are true but the hold has not elapsed. **Firing** means they have persisted throughout the hold. A false condition resets Pending and resolves Firing on the next evaluation. **Inactive** can indicate recovery, low traffic, or absent data; establish which before closing an incident. Alertmanager delivers firing/resolved notifications to an internal Docker webhook logger. No external notification destination is configured; alert evaluation and webhook delivery require separate verification.

## Timeline and evidence capture

Record the incident start, first Pending, first Firing, mitigation, and verified recovery times with timezone. Use **Unknown** for missing events; do not backdate them from the five-minute hold.

PowerShell can capture a current timestamp:

```powershell
Get-Date -Format o
(Invoke-RestMethod http://localhost:9090/api/v1/alerts).data.alerts |
    Select-Object state,activeAt,labels,annotations
```

`activeAt` is the active alert's start, not necessarily the incident start. Save actual query outputs, relevant log excerpts, simulator totals, and the commands used. Record expected and observed values separately. Log absence is not proof that requests succeeded.

## Investigation using PromQL and Docker logs

### 1. Confirm service and monitoring health

From the project folder in Windows PowerShell:

```powershell
docker compose ps
Invoke-RestMethod -Uri "http://localhost:8000/health" -TimeoutSec 5
Invoke-RestMethod -Uri "http://localhost:8000/api/orders" -TimeoutSec 5
```

**Expected:** running services and HTTP 200 responses with health JSON and sample order data. Record actual failures instead of treating these checks as automatically successful.

In Prometheus:

```promql
up{job="flask-api"}
```

1 indicates the last scrape succeeded, 0 indicates failure, and no series requires checking target/configuration state. Confirm rule health is `ok` at `/rules`, or inspect:

```powershell
(Invoke-RestMethod http://localhost:9090/api/v1/rules).data.groups |
    ForEach-Object { $_.rules } |
    Where-Object { $_.name -eq "FlaskHighErrorRate" } |
    Select-Object name,state,health,lastError
```

### 2. Measure recent error ratio and traffic

```promql
100 * (
  sum by (job) (rate(flask_http_requests_total{job="flask-api",endpoint!="/health",endpoint!="/metrics",status=~"5.."}[5m]))
  /
  sum by (job) (rate(flask_http_requests_total{job="flask-api",endpoint!="/health",endpoint!="/metrics"}[5m]))
)
```

This converts the rolling five-minute error ratio to percent. Apply `rate` per counter before summing; it accounts for resets. No 5xx series can give no result, so consult the zero-filled dashboard display and the traffic queries below. Do not interpret no data as zero errors or successful availability.

```promql
sum by (job) (increase(flask_http_requests_total{job="flask-api",endpoint!="/health",endpoint!="/metrics"}[5m]))
```

This estimated request count must be at least 20 for the alert. Boundary extrapolation can yield fractional counts.

```promql
sum by (job) (rate(flask_http_requests_total{job="flask-api",endpoint!="/health",endpoint!="/metrics"}[1m]))
```

This recent requests/second value must be positive. Together these queries explain the alert's ratio, volume, and activity guards. The separate `for: 5m` requires every guard to remain true continuously; exactly 5% does not trigger.

### 3. Identify affected endpoints and inspect logs

```promql
sum by (endpoint, method, status) (rate(flask_http_requests_total{job="flask-api",endpoint!="/health",endpoint!="/metrics",status=~"5.."}[5m]))
```

This groups 5xx requests/second by endpoint, method, and status. Compare with total traffic grouped the same way without the status filter. Do not add a status selector to histogram queries: that label does not exist there.

```powershell
docker compose logs --since=10m --tail=200 api
docker compose logs --since=10m --tail=100 prometheus
docker compose logs --since=10m --tail=100 alertmanager webhook-receiver
```

Adjust the window to cover the actual incident. Correlate access-log statuses, route names, and timestamps with metrics. Preserve useful excerpts before restarting. The intentional `/api/error` handler returns JSON with HTTP 500 without raising an exception, so a traceback is not expected or necessary evidence of this simulated failure.

## Root cause assessment

For the documented exercise, root cause was intentional simulated failures. In a new incident, verify whether a simulator is running and whether `/api/error` dominates failures before making that conclusion. Check other endpoints, recent code/configuration changes, and actual log evidence. Do not attribute an unverified incident to a database, dependency, or resource failure.

## Mitigation and recovery

For deliberate simulated failures:

1. Stop the generator with **Ctrl+C** in its terminal, or let its bounded duration finish. Preserve final counts.
2. Send healthy eligible API traffic; health probes alone are excluded from the ratio:

   ```powershell
   1..120 | ForEach-Object {
       Invoke-WebRequest -Uri "http://localhost:8000/api/orders" -UseBasicParsing -TimeoutSec 5 | Out-Null
       Start-Sleep -Milliseconds 500
   }
   ```

3. Watch the error percentage and alert state. Healthy responses dilute the ratio, and older errors age out over the five-minute window. Resolution time depends on the traffic history; it is not guaranteed by the two-minute healthy loop.

For unexpected failures, capture evidence first. Revert a confirmed faulty change and restore known-good code. If evidence shows a stuck process, `docker compose restart api` restarts the existing container without installation. Restarting cannot fix incorrect code or remove `/api/error`'s intentional behavior. A rebuild after code changes can install dependencies, so obtain approval before that operation. Do not lower the alert threshold, erase metric history, or delete volumes to make the alert disappear.

The completed incident's verified recovery actions were stopping simulated failures and sending healthy API requests. No restart or rollback was confirmed for that incident.

## Verification and closure

- Confirm health and orders responses are HTTP 200, scraping succeeds (`up = 1`), and the rule health is `ok`.
- Confirm positive recent eligible traffic. While traffic remains meaningful, verify the five-minute error percentage is at or below 5% and no affected normal endpoint continues returning unexpected 5xx responses.
- Confirm the alert is INACTIVE at `/alerts`. Query `ALERTS{alertname="FlaskHighErrorRate",alertstate=~"pending|firing"}`: active states have value 1; inactive alerts have no active series. Absence alone does not prove recovery.
- Review the dashboard and capture actual recovery evidence and timestamps. The rolling 30-day error budget retains incident failures; an inactive short-window alert does not establish SLO compliance.

For a controlled configuration check, using the existing container tool without installing anything:

```powershell
docker compose exec -T prometheus promtool check config /etc/prometheus/prometheus.yml
```

Record any verification that was not performed as **Unknown** or **Not verified**.

## Lessons learned and prevention improvements

The reported exercise demonstrated the alert lifecycle under deliberate high-error traffic. A healthy liveness route is not sufficient proof of user API recovery; positive traffic and working telemetry are also needed. Unknown timestamps and missing saved logs limit timing and impact conclusions.

Proposed follow-ups, not implemented by this runbook:

- Capture timestamped alert transitions, logs, PromQL snapshots, and request totals during future exercises.
- Keep failure generation local and intentional; restrict demo endpoints before nonlocal deployment.
- Maintain synthetic rule tests for threshold, hold, traffic guards, and exclusions.
- Consider separate scrape-failure checks and external request monitoring to cover blind spots.
- Evaluate SLO burn-rate alerts separately from the existing >5% high-error rule.

For an explicitly planned repeat exercise only:

```powershell
# Intentional failures: seven minutes, one sequential request/second by default.
py -3 scripts/simulate_incident.py
```

**Expected:** approximately 70% errors for complete cycles without other traffic, then Pending and Firing if every guard remains true for five minutes. **Observed:** must be recorded anew; the earlier success does not guarantee the next run's measurements. This consumes the local 30-day error budget and is not a recovery command.
