# Flask request-based availability SLO

## Definition and measurement status

**Objective:** at least **99.9%** of eligible requests return a non-5xx HTTP response over a **rolling 30-day window**. This is a request-based objective, not a guarantee of uptime or a calendar-month report.

Eligible requests use `flask_http_requests_total{job="flask-api",endpoint!="/health",endpoint!="/metrics"}`. All methods and other endpoints are included, including unmatched routes, optional test routes, and intentional simulation failures. Successful means `status!~"5.."`; 4xx responses count as successful for this definition. Failures use `status=~"5.."`.

The existing service dashboard remains available. Its two long-window panels are explicitly labeled as potentially partial. The new **SRE - Flask Availability SLO** dashboard separates:

- **Partial previews:** available-history calculations within a 30-day lookback, clearly labeled as observations rather than completed SLO results.
- **History-gated results:** availability, consumed budget, and remaining budget displayed only after the observation check passes and eligible traffic is positive.
- **Target:** a constant 99.9%, displayed even when measured data is absent. A target is not an achieved result.

The history status starts accumulating evidence when the new recording rules are installed. Older raw metrics can contribute to previews but cannot retroactively satisfy this observation check. Current history is not assumed to span 30 days.

## Calculations and recording rules

`monitoring/prometheus/rules/flask-slo.yml` evaluates every 15 seconds. The rules use `increase` on each original counter series **before** aggregation, preserving reset handling. Derived recording metrics are gauges: do not apply `rate` or `increase` to their totals again.

| Symbol | Recording metric | Calculation |
| --- | --- | --- |
| T | `flask:slo_eligible_requests:increase30d` | Sum of eligible counter increases over 30d |
| F | `flask:slo_5xx_requests:increase30d` | Sum of eligible 5xx counter increases over 30d |
| G | `flask:slo_successful_requests:increase30d` | Sum of eligible non-5xx counter increases over 30d |
| A | `flask:slo_error_budget_allowance:30d` | `0.001 × T` allowed failed requests |
| SLI | `flask:slo_availability_percent:30d` | `100 × G / T`, only when T > 0 |
| Consumed | `flask:slo_error_budget_consumed_percent:30d` | `100 × F / A`, only when A > 0 |
| Remaining | `flask:slo_error_budget_remaining_percent:30d` | `100 − Consumed` |

Remaining requests are `A − F`. Negative remaining values indicate overspending. Consumed can exceed 100%; neither is clamped. The budget is an allowance of failed **requests**, not downtime minutes. Changing total traffic changes the budget allowance, so percentages can improve through healthy traffic even while previous failures remain in the window.

Raw total expression:

```promql
sum(increase(flask_http_requests_total{job="flask-api",endpoint!="/health",endpoint!="/metrics"}[30d]))
```

Failure expression with a conditional zero fallback:

```promql
sum(increase(flask_http_requests_total{job="flask-api",endpoint!="/health",endpoint!="/metrics",status=~"5.."}[30d]))
or (0 * flask:slo_eligible_requests:increase30d)
```

The success expression uses the same structure with `status!~"5.."`. The fallback represents zero only when a usable total series exists. It does not turn an entirely missing service into zero requests or successful availability.

```promql
100 * flask:slo_successful_requests:increase30d
  / (flask:slo_eligible_requests:increase30d > 0)

0.001 * flask:slo_eligible_requests:increase30d

100 * flask:slo_5xx_requests:increase30d
  / (flask:slo_error_budget_allowance:30d > 0)

100 - flask:slo_error_budget_consumed_percent:30d

flask:slo_error_budget_allowance:30d - flask:slo_5xx_requests:increase30d
```

Comparisons without `bool` filter out zero denominators while preserving positive values. With zero traffic, the ratio/budget percentage series are absent; the dashboard shows no traffic/unverified rather than 100%. Request totals and allowance may legitimately be zero.

### History evidence and result gating

`flask:slo_observation_valid` is 1 only when the Flask scrape succeeds, the scrape timestamp is less than 30 seconds old, and at least one eligible counter series is present. Missing evidence produces 0. This is sampled monitoring evidence, not proof that every request was counted.

`flask:slo_observation_coverage_percent:30d` is:

```promql
100 * count_over_time(flask:slo_observation_valid[30d]) / 172800
```

Thirty days at a 15-second evaluation interval require 172800 observations. This percentage measures **recorded samples**, including invalid samples; a full coverage percentage alone is not readiness.

Readiness requires all of the following:

```promql
(min_over_time(flask:slo_observation_valid[30d]) == bool 1)
* (count_over_time(flask:slo_observation_valid[30d]) >= bool 172800)
* (flask:slo_observation_valid == bool 1)
* ((count(present_over_time(flask:slo_observation_valid[1m] offset 30d)) > bool 0) or vector(0))
```

The minimum rejects any invalid observation; the count rejects missing rule evaluations; the current value rejects a currently invalid observation. The offset witness requires an observation at least 30 days ago, preventing an off-by-one-sample early result. `bool` produces 0/1 flags. The dashboard maps readiness 0 or absent to **PARTIAL / UNVERIFIED**, and 1 to **30d observation check passed**. Failed/missed observations keep this conservative gate closed until they leave the rolling window. Readiness does not imply SLO compliance: a fully measured SLI may still fall below 99.9%.

Full-window panels use:

```promql
flask:slo_availability_percent:30d and on () (flask:slo_window_ready == 1)
flask:slo_error_budget_consumed_percent:30d and on () (flask:slo_window_ready == 1)
flask:slo_error_budget_remaining_percent:30d and on () (flask:slo_window_ready == 1)
```

`and on ()` filters the unlabeled aggregate results by the readiness flag; it does not replace them with that flag. The target uses `vector(99.9)`.

### Limitations, resets, and low traffic

- API restarts reset in-memory counters. `increase` detects decreases per series and estimates the positive increments across observed resets. Requests between the last scrape and a reset can be lost; unseen multiple resets cannot be reconstructed.
- `increase` extrapolates around sample boundaries and can yield fractional counts. Values are monitoring estimates, not an exact transaction ledger. A newly created status series needs at least two samples, and its initial unsampled count can be missed.
- Thirty days of retention is not the same as thirty days of samples. The existing 35-day retention helps preserve the window but cannot restore deleted history.
- A successful scrape and some eligible metrics do not prove every status/endpoint series remained present. The history gate cannot detect all disappearing counter series, failures between scrapes, or requests that never reached Flask. Do not treat its passed status as an audit of exact request completeness.
- Low traffic still has a mathematically valid SLI when T > 0, but is statistically fragile. At 100 requests, one failure means 99% availability and 1000% budget consumption. No arbitrary traffic floor is added to SLO accounting; the alert's minimum-20 guard is separate.
- Monitoring failures make the history unverified, not silently successful. A historical preview can remain visible during a current scrape failure; always check the history and scrape panels.
- Simulation failures deliberately consume the same local error budget. Resolving `FlaskHighErrorRate` or receiving a resolved webhook does not reset the 30-day SLO.

## Worked examples

Illustrative arithmetic below is **not observed project telemetry**. Full-window conclusions additionally require complete history.

| Eligible T | Failures F | Successful G | Allowance A | Availability | Consumed | Remaining |
| --- | --- | --- | --- | --- | --- | --- |
| 1000000 | 0 | 1000000 | 1000 | 100% | 0% | 100% |
| 1000000 | 500 | 999500 | 1000 | 99.95% | 50% | 50% |
| 1000000 | 1000 | 999000 | 1000 | 99.9% | 100% | 0% |
| 1000000 | 2000 | 998000 | 1000 | 99.8% | 200% | -100% |
| 100 | 1 | 99 | 0.1 | 99% | 1000% | -900% |
| 0 | 0 | 0 | 0 | Undefined | Undefined | Undefined |

At one million requests and 500 failures, 500 allowed failed requests remain. At 2000 failures, the allowance is exceeded by 1000 requests. If the same totals cover only two days, they are provisional two-day observations within the lookback, not a completed 30-day SLO result.

## Validate and apply locally on Windows PowerShell

No additional package, container, or image is required. Validate with the existing Prometheus tools:

```powershell
docker compose exec -T prometheus promtool check config /etc/prometheus/prometheus.yml
docker compose exec -T prometheus mkdir -p /tmp/slo-validation
docker compose cp ./tests/prometheus/flask-slo.test.yml prometheus:/tmp/slo-validation/flask-slo.test.yml
docker compose cp ./tests/prometheus/flask-slo-history.test.yml prometheus:/tmp/slo-validation/flask-slo-history.test.yml
docker compose exec -T prometheus promtool test rules /tmp/slo-validation/flask-slo.test.yml /tmp/slo-validation/flask-slo-history.test.yml
docker compose kill -s SIGHUP prometheus
(Invoke-RestMethod http://localhost:9090/api/v1/status/runtimeinfo).data.reloadConfigSuccess
(Invoke-RestMethod http://localhost:9090/api/v1/rules).data.groups | Select-Object name
```

Calculation tests cover endpoint exclusions, no 5xx series, all failures, zero/missing data, and counter resets. History tests scale 30 days/172800 samples to one minute/four samples to validate the same gating structure without exceeding promtool query sample limits. The production rule retains the full 30-day/172800 constants. Synthetic tests are not evidence that the running project has accumulated 30 days.

Open http://localhost:3000/d/sre-flask-availability-slo/sre-flask-availability-slo after Grafana's 30-second provisioning poll. Check that status is PARTIAL / UNVERIFIED initially, the target is 99.9%, previews show available data, and full-window result panels have no result. Dashboard stat queries are instant queries so old values are not reused as current measurements.

Check any recording metric using Prometheus, for example:

```powershell
$query = [Uri]::EscapeDataString('flask:slo_window_ready')
(Invoke-RestMethod "http://localhost:9090/api/v1/query?query=$query").data.result
```

Cross-check T approximately equals G + F, allowance equals 0.001 × T, and remaining plus consumed equals 100 when percentages exist. New rules can take an evaluation cycle to become visible. No live incident generation is needed to validate arithmetic. The existing alert rule and Alertmanager/webhook routing are unchanged.

Counter calculations follow [Prometheus query functions](https://prometheus.io/docs/prometheus/latest/querying/functions/).

## Implementation validation results

- Production configuration and all ten SLO recording rules passed `promtool` checks; live rule health is `ok` and Prometheus reload succeeded.
- Seven calculation fixtures and two scaled-history fixtures passed. Production constants were checked separately: 15-second evaluations, 172800 observations, and a 30-day boundary witness.
- Live observed totals reconciled as T = G + F, allowance = 0.001 × T, and consumed + remaining = 100%. These are available-history observations, not a completed 30-day SLO result.
- Live readiness was 0; all three full-window panels correctly returned no result. Preview/target queries returned data and Grafana automatically provisioned the new dashboard. The existing six-panel service overview was preserved.
- No dependency installation, image download, container restart, alert threshold change, or incident generation was needed. Thirty days of complete history were not available or claimed.
