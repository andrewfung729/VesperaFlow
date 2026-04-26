"""Shared route helpers."""

from pathlib import Path


def observed_version(body_version: int | None, if_match: str | None) -> int:
    if body_version is not None:
        return body_version
    if if_match is None:
        raise ValueError("version is required")
    return int(if_match.strip('"'))


def require_existing_absolute_directory(value: str) -> str:
    path = Path(value).expanduser()
    if not path.is_absolute():
        raise ValueError("target_working_directory must be an absolute path")
    if not path.exists():
        raise ValueError("target_working_directory does not exist")
    if not path.is_dir():
        raise ValueError("target_working_directory must be a directory")
    return str(path.resolve())


def optional_existing_absolute_directory(value: str | None) -> str | None:
    if value is None:
        return None
    return require_existing_absolute_directory(value)
