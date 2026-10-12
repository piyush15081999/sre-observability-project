# Contributing

This is a local SRE learning and demonstration project. Keep contributions small, reproducible, and supported by evidence.

1. Describe the problem and intended behavior before changing code.
2. Preserve metric names/labels, localhost-only host ports, internal webhook access, and partial-history protection unless the proposed change explicitly addresses them.
3. Add meaningful tests for changed behavior. Use existing dependencies locally; ask before installing packages or pulling images in a shared workspace.
4. Follow the test commands in [README.md](README.md). Run `py -3 -B scripts/check_project.py` for documentation/dashboard checks and a heuristic secret review.
5. Update relevant documentation. Separate observed results, test results, and expected behavior. Never invent incident timestamps, log excerpts, or screenshots.
6. Submit a change description covering the problem, implementation, tests, and remaining limitations. Do not commit `.env`, credentials, unredacted logs, or generated files.

The CI workflow installs dependencies only on an ephemeral GitHub runner and never deploys. A successful synthetic test is not evidence of a completed live incident or a full 30-day SLO window.

The repository currently has no license, by the author's choice. Public visibility alone does not grant an open-source reuse license. Resolve licensing with the author before redistributing or contributing code that requires particular licensing terms.
