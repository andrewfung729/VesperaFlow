"""Agent-first repository health checks.

These checks keep the repo legible to coding agents and enforce the first set
of architectural guardrails that are cheap to verify statically.
"""

from __future__ import annotations

import re
import subprocess
import sys
from datetime import UTC, date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REQUIRED_NONEMPTY_FILES = [
    "AGENTS.md",
    "README.md",
    "docs/README.md",
    "docs/MVP_PROGRESS.md",
    "docs/QUALITY.md",
    "docs/executor-profiles.md",
    "docs/plans/README.md",
    "docs/plans/TEMPLATE.md",
    "docs/generated/README.md",
    "apps/api/README.md",
    "apps/worker/README.md",
    "apps/web/README.md",
    "packages/core/README.md",
    "packages/store/README.md",
    "tests/README.md",
]

REQUIRED_DIRS = [
    "docs/plans/active",
    "docs/plans/completed",
    "docs/generated",
]

REQUIRED_AGENT_REFERENCES = [
    "docs/architecture.md",
    "docs/MVP_PROGRESS.md",
    "docs/temporal-architecture.md",
    "docs/executor-profiles.md",
    "docs/domain-model.md",
    "docs/api-spec.md",
    "tests/README.md",
]

SOURCE_SUFFIXES = {".py", ".ts", ".vue"}
SOURCE_ROOTS = ["apps", "packages"]

FORBIDDEN_SCHEDULER_PATTERNS = [
    (
        re.compile(r"\bcron\b", re.IGNORECASE),
        "Temporal is the sole scheduler; do not add cron-based scheduling.",
    ),
    (
        re.compile(r"\bAPScheduler\b|\bapscheduler\b"),
        "Temporal is the sole scheduler; do not add APScheduler.",
    ),
    (
        re.compile(r"\bCelery\s+beat\b|\bcelery\.schedules\b", re.IGNORECASE),
        "Temporal is the sole scheduler; do not add Celery beat scheduling.",
    ),
    (
        re.compile(r"\basyncio\.sleep\s*\("),
        "Temporal owns delayed execution; do not implement scheduler sleep loops.",
    ),
]

GENERATED_FACTS = {
    "docs/generated/api-routes.md": [
        "apps/api/src/vesperaflow_api/app.py",
        "apps/api/src/vesperaflow_api/routes",
        "apps/api/src/vesperaflow_api/schemas",
    ],
    "docs/generated/db-schema.md": [
        "packages/store/src/vesperaflow_store/models.py",
        "packages/store/alembic/versions",
    ],
    "docs/generated/dependency-graph.md": [
        "pyproject.toml",
        "apps/api/pyproject.toml",
        "apps/worker/pyproject.toml",
        "packages/core/pyproject.toml",
        "packages/store/pyproject.toml",
    ],
    "docs/generated/temporal-surface.md": [
        "apps/api/src/vesperaflow_api/temporal_scheduler.py",
        "apps/worker/src/vesperaflow_worker/main.py",
        "apps/worker/src/vesperaflow_worker/workflows",
        "apps/worker/src/vesperaflow_worker/activities",
        "packages/core/src/vesperaflow_core/contracts.py",
    ],
}

GENERATED_COMMAND = "uv run python scripts/generate_agent_facts.py"


def fail(message: str, errors: list[str]) -> None:
    errors.append(message)


def relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def check_required_files(errors: list[str]) -> None:
    for name in REQUIRED_NONEMPTY_FILES:
        path = ROOT / name
        if not path.exists():
            fail(f"Missing required file: {name}", errors)
            continue
        if path.stat().st_size < 40:
            fail(f"Required file is effectively empty: {name}", errors)


def check_required_dirs(errors: list[str]) -> None:
    for name in REQUIRED_DIRS:
        path = ROOT / name
        if not path.is_dir():
            fail(f"Missing required directory: {name}", errors)


def check_agents_file(errors: list[str]) -> None:
    path = ROOT / "AGENTS.md"
    if not path.exists():
        return

    text = path.read_text(encoding="utf-8")
    line_count = len(text.splitlines())
    if line_count > 150:
        fail(f"AGENTS.md is {line_count} lines; keep it under 150 lines.", errors)

    for ref in REQUIRED_AGENT_REFERENCES:
        if ref not in text:
            fail(f"AGENTS.md must point agents to {ref}", errors)
        elif not (ROOT / ref).exists():
            fail(f"AGENTS.md references missing path: {ref}", errors)


def check_env_example(errors: list[str]) -> None:
    env_path = ROOT / "infra/.env"
    tracked_env = subprocess.run(
        ["git", "ls-files", "infra/.env"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if tracked_env and env_path.exists():
        fail(
            "infra/.env should be local-only; commit infra/.env.example instead.",
            errors,
        )
    if not (ROOT / "infra/.env.example").exists():
        fail("Missing infra/.env.example for local compose version pins.", errors)


def iter_source_files() -> list[Path]:
    files: list[Path] = []
    for source_root in SOURCE_ROOTS:
        root = ROOT / source_root
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if "node_modules" in path.parts or "dist" in path.parts:
                continue
            if path.is_file() and path.suffix in SOURCE_SUFFIXES:
                files.append(path)
    return files


def check_forbidden_scheduler_patterns(errors: list[str]) -> None:
    for path in iter_source_files():
        lines = path.read_text(encoding="utf-8").splitlines()
        for lineno, line in enumerate(lines, start=1):
            for pattern, message in FORBIDDEN_SCHEDULER_PATTERNS:
                if pattern.search(line):
                    # Allow asyncio.sleep inside Temporal heartbeat loops
                    if "asyncio.sleep" in line:
                        context = "\n".join(lines[max(0, lineno - 10) : lineno])
                        if "heartbeat" in context or "_heartbeat_loop" in context:
                            continue
                    fail(f"{relative(path)}:{lineno}: {message}", errors)


def check_generated_facts(errors: list[str]) -> None:
    for generated_name, source_names in GENERATED_FACTS.items():
        generated_path = ROOT / generated_name
        if not generated_path.exists():
            fail(f"Missing generated fact snapshot: {generated_name}", errors)
            continue

        text = generated_path.read_text(encoding="utf-8")
        generated_at = _generated_date(text)
        if generated_at is None:
            fail(
                f"{generated_name} must include '- Generated: YYYY-MM-DD' "
                "in its header.",
                errors,
            )
        elif generated_at > datetime.now(UTC).date():
            fail(f"{generated_name} has a future generated date.", errors)
        if f"- Regenerate: `{GENERATED_COMMAND}`" not in text:
            fail(
                f"{generated_name} must include the regenerate command "
                f"`{GENERATED_COMMAND}`.",
                errors,
            )

        source_paths = _existing_source_paths(source_names)
        if not source_paths:
            fail(f"{generated_name} has no existing source paths to check.", errors)
            continue
        newest_source_mtime = max(path.stat().st_mtime for path in source_paths)
        if generated_path.stat().st_mtime + 1 < newest_source_mtime:
            newest_source = max(source_paths, key=lambda path: path.stat().st_mtime)
            fail(
                f"{generated_name} is older than {relative(newest_source)}; "
                f"run `{GENERATED_COMMAND}`.",
                errors,
            )


def _generated_date(text: str) -> date | None:
    match = re.search(r"^- Generated: (\d{4}-\d{2}-\d{2})$", text, re.MULTILINE)
    if match is None:
        return None
    try:
        return datetime.strptime(match.group(1), "%Y-%m-%d").date()
    except ValueError:
        return None


def _existing_source_paths(names: list[str]) -> list[Path]:
    paths: list[Path] = []
    for name in names:
        path = ROOT / name
        if path.is_file():
            paths.append(path)
        elif path.is_dir():
            paths.extend(
                item
                for item in path.rglob("*")
                if item.is_file()
                and "node_modules" not in item.parts
                and "__pycache__" not in item.parts
            )
    return paths


def main() -> int:
    errors: list[str] = []
    check_required_files(errors)
    check_required_dirs(errors)
    check_agents_file(errors)
    check_env_example(errors)
    check_forbidden_scheduler_patterns(errors)
    check_generated_facts(errors)

    if errors:
        print("Agent repo checks failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print("Agent repo checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
