"""Check publication files, dashboard JSON, and likely secrets without packages.

This is a heuristic working-tree check, not a full secret scanner or Git history
audit. It reports filenames only and never prints potential credential values.
"""

import ast
import json
from pathlib import Path
import re
import sys
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
EXCLUDED_DIRS = {".git", ".venv", "venv", "__pycache__", ".pytest_cache",
                 ".aws", ".codex", ".agents", ".idea", ".vscode", "secrets",
                 "logs", "artifacts", "build", "dist", "htmlcov"}
TOKEN_PATTERN = re.compile(
    r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|"
    r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b|"
    r"\bgh[pousr]_[A-Za-z0-9]{30,}\b|\bgithub_pat_[A-Za-z0-9_]{40,}\b"
)


def main():
    errors = []
    files = [p for p in ROOT.rglob("*") if p.is_file()
             and not any(part in EXCLUDED_DIRS or part.endswith(".egg-info")
                         for part in p.relative_to(ROOT).parts)
             and not (p.name.startswith(".env") and p.name != ".env.example")
             and p.suffix not in {".pem", ".key", ".log", ".pyc", ".pyo"}]
    # Detect accidental reuse of the local Grafana password in publication files.
    # Never report the password itself; short/common values are not searched.
    local_values = []
    env_file = ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8-sig").splitlines():
            if line.startswith("GRAFANA_ADMIN_PASSWORD="):
                value = line.split("=", 1)[1].strip().strip("\"'")
                if len(value) >= 8 and value != "replace-with-a-strong-local-password":
                    local_values.append(value)
        print("Local .env exists; excluded from publication scan and must remain untracked.")

    for path in files:
        relative = path.relative_to(ROOT).as_posix()
        try:
            content = path.read_text(encoding="utf-8-sig")
        except UnicodeError:
            continue  # Screenshots require manual pixel/metadata review.
        if TOKEN_PATTERN.search(content) or any(value in content for value in local_values):
            errors.append(f"Potential secret in {relative}; inspect privately and rotate if exposed.")
        if path.suffix == ".py":
            try:
                ast.parse(content, filename=relative)
            except SyntaxError:
                errors.append(f"Python syntax error in {relative}")
        if path.suffix == ".md":
            if len(re.findall(r"(?m)^\s*```", content)) % 2:
                errors.append(f"Unbalanced code fences in {relative}")
            # Check local Markdown links; skip URLs, fragments, and fenced code.
            prose = re.sub(r"```.*?```", "", content, flags=re.S)
            for target in re.findall(r"\]\(([^)]+)\)", prose):
                target = target.strip().strip("<>").split("#", 1)[0]
                if not target or re.match(r"[a-zA-Z][a-zA-Z0-9+.-]*:", target):
                    continue
                if not (path.parent / unquote(target)).exists():
                    errors.append(f"Broken local link in {relative}")

    dashboards = list((ROOT / "monitoring/grafana/dashboards").glob("*.json"))
    uids = set()
    for path in dashboards:
        try:
            dashboard = json.loads(path.read_text(encoding="utf-8"))
            uid = dashboard["uid"]
            if uid in uids:
                errors.append("Duplicate dashboard UID")
            uids.add(uid)
            if dashboard["time"] != {"from": "now-15m", "to": "now"}:
                errors.append(f"Unexpected dashboard time range in {path.name}")
            for panel in dashboard["panels"]:
                for target in panel.get("targets", []):
                    if target["datasource"]["uid"] != "prometheus":
                        errors.append(f"Unexpected data source in {path.name}")
        except (ValueError, KeyError):
            errors.append(f"Invalid dashboard structure in {path.name}")

    slo = (ROOT / "monitoring/prometheus/rules/flask-slo.yml").read_text(encoding="utf-8")
    for required in ("interval: 15s", ">= bool 172800", "offset 30d"):
        if required not in slo:
            errors.append("SLO production history constants changed; review required")
    for filename in (".gitignore", ".dockerignore"):
        lines = (ROOT / filename).read_text(encoding="utf-8").splitlines()
        if not all(pattern in lines for pattern in (".env", ".env.*", "!.env.example")):
            errors.append(f"Missing environment-file exclusions in {filename}")

    if errors:
        for error in sorted(set(errors)):
            print(error)
        return 1
    print(f"Checked {len(files)} candidate files and {len(dashboards)} dashboards: passed.")
    print("No likely secrets detected by this heuristic; Git history and images were not scanned.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
