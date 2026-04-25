"""Time normalization helpers."""

from datetime import UTC, datetime


def utc_now() -> datetime:
    return datetime.now(UTC)


def to_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("datetime must include an explicit timezone")
    return value.astimezone(UTC)
