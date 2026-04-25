"""Agent-first repository health checks.

These checks keep the repo legible to coding agents and enforce the first set
of architectural guardrails that are cheap to verify statically.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REQUIRED_NONEMPTY_FILES = [
    "AGENTS.md",
    "README.md",
    "docs/README.md",
    "docs/MVP_PROGRESS.md",
    "docs/QUALITY.md",
    "docs/plans/README.md",
    "docs/plans/TEMPLATE.md",
    "docs/generated/README.md",
    "apps/api/README.md",
    "apps/worker/README.md",
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
        text = path.read_text(encoding="utf-8")
        for lineno, line in enumerate(text.splitlines(), start=1):
            for pattern, message in FORBIDDEN_SCHEDULER_PATTERNS:
                if pattern.search(line):
                    fail(f"{relative(path)}:{lineno}: {message}", errors)


def main() -> int:
    errors: list[str] = []
    check_required_files(errors)
    check_required_dirs(errors)
    check_agents_file(errors)
    check_env_example(errors)
    check_forbidden_scheduler_patterns(errors)

    if errors:
        print("Agent repo checks failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print("Agent repo checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
