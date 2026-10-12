# Portfolio screenshot capture guide

No screenshots are included yet. Capture real evidence from the local running stack; do not manufacture values or relabel partial history as a full 30-day result. Suggested filenames below are plans, not links to nonexistent files.

| Suggested filename | Capture | What it demonstrates |
| --- | --- | --- |
| `service-overview.png` | SRE - Flask Service Overview, with visible time range and units | Request rate, error percentage, latency, and short-window availability |
| `slo-partial-history.png` | SRE - Flask Availability SLO, including history status and empty full-window panels | Honest partial-window reporting and provisional budget calculations |
| `prometheus-target.png` | Flask target status and job label | Successful metric scraping at capture time |
| `alert-pending.png` | FlaskHighErrorRate in Pending with rule details | Sustained-condition hold before Firing |
| `alert-firing.png` | FlaskHighErrorRate in Firing with query context | Successful alert evaluation during a planned simulation |
| `webhook-delivery.png` | Redacted receiver logs showing the same alert's firing and resolved notifications | Notification delivery independently of Prometheus evaluation |
| `recovery.png` | Healthy orders responses plus recent traffic/error graph and inactive rule | Recovery evidence; an inactive alert alone is insufficient |

Use a planned local simulation and the [incident runbook](../incident-runbook.md). Record the command, timestamp with timezone, dashboard range, and whether each capture is from the same exercise. Preserve unknown times as unknown; do not assign new captures to the earlier untimestamped incident.

Before committing an image:

- Redact passwords, tokens, cookies, Authorization headers, environment values, account identifiers, personal paths/usernames, email addresses, and sensitive browser tabs.
- Keep alert name, status, units, relevant metric labels, and measurement-history warnings visible.
- Review both pixels and image metadata. Use an irreversible redaction and verify the exported image; a movable overlay is insufficient.
- Use PNG or another ordinary image format. Avoid raw credential-bearing log/configuration exports.
- Caption actual observations, including partial history and intentionally generated failures. Do not claim production performance or a completed 30-day SLO.

After adding and reviewing real files, add relative image links to the main README. Until then, the main README links only to this capture guide.
