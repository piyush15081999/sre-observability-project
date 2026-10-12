# GitHub portfolio preparation review

## Scope

The project was prepared as a local SRE learning and demonstration repository. No API, metric definition, dashboard, alert rule, SLO calculation, Alertmanager configuration, or webhook receiver behavior was changed.

The README was rewritten for a new reader; ignore rules and the credential template were clarified; contributor and screenshot guidance were added; stale incident-document notification statements were updated; and CI/publication checks were added. The author chose to leave the repository unlicensed.

## Validation results

| Check | Result |
| --- | --- |
| Python endpoint and webhook tests | Five tests passed using the existing API container's dependencies |
| Prometheus synthetic fixtures | All three fixture files passed: alert lifecycle/guards, SLO calculations, scaled history gating |
| Compose | Quiet configuration validation passed |
| Prometheus | Configuration, one alert rule, and ten SLO recording rules validated |
| Alertmanager | Configuration/routing validated |
| Publication checker | Local documentation links, Python syntax, dashboard JSON, ignore patterns, and selected production SLO constants passed |
| Heuristic secret check | No likely secret detected in publication candidates; local `.env` exists and is excluded |
| Git history/staged audit | Not available: the workspace is not a Git repository |
| GitHub Actions execution | Not performed: workflow file added, but nothing published or pushed |
| Screenshot review | Not performed: screenshots have not been supplied |
| Completed 30-day SLO | Not claimed; the history gate remains required |

Validation installed no packages and downloaded no images. Python/rule tests ran in temporary directories inside existing containers and did not modify the served application. No live incident was generated for this review.

The publication checker is heuristic, not a comprehensive secret scanner. It checks common private-key/token signatures and accidental copies of the local Grafana password, without printing values. It does not inspect Git history, binary artifacts, or image pixels/metadata. Recheck after adding new content.

## Before publishing

- Review all candidate and staged files; confirm `.env`, credentials, logs, and generated artifacts are excluded. An ignore rule cannot untrack previously committed files.
- If any real credential was exposed elsewhere, rotate it before publishing and remediate affected history.
- Capture actual screenshots using the [capture guide](screenshots/README.md), redact sensitive content, and add only links to files that exist.
- Keep operator-confirmed incident facts distinct from new screenshots and automated test results; unknown original timestamps remain unknown.
- State that the project is local, deliberately includes error endpoints, and has no completed 30-day SLO claim.
- Keep the license decision explicit: currently unlicensed, with no open-source reuse grant implied by visibility.
- Run the CI workflow after an intentional publication and investigate any failures. Local checks are not proof of a successful GitHub-hosted workflow run.

No repository initialization, remote creation, commit, push, deployment, or Git history change was performed.

## Suggested repository metadata

**Description:** Local Flask SRE observability lab with Prometheus, Grafana, Alertmanager webhooks, incident simulation, and availability SLO tracking.

**Topics:** `sre`, `observability`, `flask`, `prometheus`, `grafana`, `alertmanager`, `docker-compose`, `slo`, `incident-response`, `python`.
