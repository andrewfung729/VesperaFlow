"""Small RRULE subset used by the MVP recurring schedule lifecycle."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

_WEEKDAYS = {
    "MO": 0,
    "TU": 1,
    "WE": 2,
    "TH": 3,
    "FR": 4,
    "SA": 5,
    "SU": 6,
}
_SUPPORTED_FIELDS = frozenset(
    {"FREQ", "INTERVAL", "BYSECOND", "BYMINUTE", "BYHOUR", "BYDAY"}
)
_FIELDS_BY_FREQUENCY = {
    "HOURLY": frozenset({"FREQ", "INTERVAL", "BYSECOND", "BYMINUTE"}),
    "DAILY": frozenset(
        {"FREQ", "INTERVAL", "BYSECOND", "BYMINUTE", "BYHOUR"}
    ),
    "WEEKLY": _SUPPORTED_FIELDS,
}


@dataclass(frozen=True, slots=True)
class RecurrenceSpec:
    freq: str
    hours: tuple[int, ...]
    minutes: tuple[int, ...]
    seconds: tuple[int, ...]
    weekdays: tuple[int, ...]


def parse_recurrence_rule(value: str) -> RecurrenceSpec:
    rule = value.removeprefix("RRULE:")
    parts: dict[str, str] = {}
    for raw_part in rule.split(";"):
        if not raw_part:
            continue
        key, separator, raw_value = raw_part.partition("=")
        if not separator or not key or not raw_value:
            raise ValueError("recurrence_rule must be an iCalendar RRULE string")
        normalized_key = key.upper()
        if normalized_key in parts:
            raise ValueError(
                f"recurrence_rule contains duplicate field {normalized_key}"
            )
        parts[normalized_key] = raw_value.upper()

    unsupported_fields = sorted(set(parts) - _SUPPORTED_FIELDS)
    if unsupported_fields:
        raise ValueError(
            "recurrence_rule contains unsupported field(s): "
            + ", ".join(unsupported_fields)
        )

    freq = parts.get("FREQ")
    if freq not in _FIELDS_BY_FREQUENCY:
        raise ValueError(
            "recurrence_rule FREQ must be HOURLY, DAILY, or WEEKLY"
        )
    if parts.get("INTERVAL", "1") != "1":
        raise ValueError(
            "recurrence_rule INTERVAL values other than 1 are not supported"
        )
    if freq == "WEEKLY" and "BYDAY" not in parts:
        raise ValueError("weekly recurrence_rule requires BYDAY")
    if freq in {"DAILY", "WEEKLY"} and "BYHOUR" not in parts:
        raise ValueError(f"{freq.lower()} recurrence_rule requires BYHOUR")

    ignored_fields = sorted(set(parts) - _FIELDS_BY_FREQUENCY[freq])
    if ignored_fields:
        raise ValueError(
            "recurrence_rule field(s) "
            + ", ".join(ignored_fields)
            + f" are not supported for {freq}"
        )

    seconds = _parse_int_list(parts.get("BYSECOND"), minimum=0, maximum=59) or (0,)
    if seconds != (0,):
        raise ValueError(
            "recurrence_rule BYSECOND values other than 0 are not supported"
        )

    hours = (
        _parse_int_list(parts.get("BYHOUR"), minimum=0, maximum=23)
        or tuple(range(24))
    )
    minutes = _parse_int_list(parts.get("BYMINUTE"), minimum=0, maximum=59) or (0,)
    weekdays = _parse_weekdays(parts.get("BYDAY"))
    _require_minimum_occurrence_spacing(
        freq=freq,
        hours=hours,
        minutes=minutes,
        seconds=seconds,
        weekdays=weekdays,
    )
    return RecurrenceSpec(
        freq=freq,
        hours=hours,
        minutes=minutes,
        seconds=seconds,
        weekdays=weekdays,
    )


def require_iana_timezone(value: str) -> None:
    try:
        _ = ZoneInfo(value)
    except ZoneInfoNotFoundError as exc:
        raise ValueError("recurrence_timezone must be a valid IANA timezone") from exc


def next_occurrence_after(
    *,
    recurrence_rule: str,
    recurrence_timezone: str,
    after: datetime,
) -> datetime:
    spec = parse_recurrence_rule(recurrence_rule)
    require_iana_timezone(recurrence_timezone)
    local_after = after.astimezone(ZoneInfo(recurrence_timezone))

    if spec.freq == "HOURLY":
        hour_start = local_after.replace(minute=0, second=0, microsecond=0)
        for hour_offset in range(0, 24 * 371):
            hour = hour_start + timedelta(hours=hour_offset)
            for minute in spec.minutes:
                for second in spec.seconds:
                    candidate = hour.replace(minute=minute, second=second)
                    if candidate > local_after:
                        return candidate.astimezone(UTC)
        raise ValueError("recurrence_rule did not produce a future occurrence")

    local_day = local_after.replace(hour=0, minute=0, second=0, microsecond=0)
    for day_offset in range(0, 371):
        day = local_day + timedelta(days=day_offset)
        if spec.freq == "WEEKLY" and day.weekday() not in spec.weekdays:
            continue
        for hour in spec.hours:
            for minute in spec.minutes:
                for second in spec.seconds:
                    candidate = day.replace(hour=hour, minute=minute, second=second)
                    if candidate > local_after:
                        return candidate.astimezone(UTC)

    raise ValueError("recurrence_rule did not produce a future occurrence")


def _parse_int_list(
    value: str | None,
    *,
    minimum: int,
    maximum: int,
) -> tuple[int, ...]:
    if value is None:
        return ()
    parsed = tuple(sorted({int(item) for item in value.split(",") if item}))
    if not parsed or any(item < minimum or item > maximum for item in parsed):
        raise ValueError("recurrence_rule contains an out-of-range numeric field")
    return parsed


def _parse_weekdays(value: str | None) -> tuple[int, ...]:
    if value is None:
        return tuple(range(7))
    try:
        return tuple(sorted({_WEEKDAYS[item] for item in value.split(",") if item}))
    except KeyError as exc:
        raise ValueError("recurrence_rule BYDAY contains an invalid weekday") from exc


def _require_minimum_occurrence_spacing(
    *,
    freq: str,
    hours: tuple[int, ...],
    minutes: tuple[int, ...],
    seconds: tuple[int, ...],
    weekdays: tuple[int, ...],
) -> None:
    if freq == "HOURLY":
        period_seconds = 60 * 60
        offsets = {minute * 60 + second for minute in minutes for second in seconds}
    elif freq == "DAILY":
        period_seconds = 24 * 60 * 60
        offsets = {
            hour * 60 * 60 + minute * 60 + second
            for hour in hours
            for minute in minutes
            for second in seconds
        }
    else:
        period_seconds = 7 * 24 * 60 * 60
        offsets = {
            weekday * 24 * 60 * 60 + hour * 60 * 60 + minute * 60 + second
            for weekday in weekdays
            for hour in hours
            for minute in minutes
            for second in seconds
        }

    ordered = sorted(offsets)
    cyclic = [*ordered[1:], ordered[0] + period_seconds]
    gaps = (next_offset - offset for offset, next_offset in zip(ordered, cyclic))
    if any(gap < 15 * 60 for gap in gaps):
        raise ValueError(
            "recurrence_rule must not fire more often than once every 15 minutes"
        )
