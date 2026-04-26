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
        parts[key.upper()] = raw_value.upper()

    freq = parts.get("FREQ")
    if freq not in {"MINUTELY", "HOURLY", "DAILY", "WEEKLY"}:
        raise ValueError(
            "recurrence_rule FREQ must be MINUTELY, HOURLY, DAILY, or WEEKLY"
        )
    if parts.get("INTERVAL", "1") != "1":
        raise ValueError(
            "recurrence_rule INTERVAL values other than 1 are not supported"
        )
    if freq == "WEEKLY" and "BYDAY" not in parts:
        raise ValueError("weekly recurrence_rule requires BYDAY")

    seconds = _parse_int_list(parts.get("BYSECOND"), minimum=0, maximum=59) or (0,)
    if seconds != (0,):
        raise ValueError(
            "recurrence_rule BYSECOND values other than 0 are not supported"
        )

    return RecurrenceSpec(
        freq=freq,
        hours=_parse_int_list(parts.get("BYHOUR"), minimum=0, maximum=23)
        or tuple(range(24)),
        minutes=_parse_int_list(parts.get("BYMINUTE"), minimum=0, maximum=59) or (0,),
        seconds=seconds,
        weekdays=_parse_weekdays(parts.get("BYDAY")),
    )


def require_iana_timezone(value: str) -> None:
    try:
        ZoneInfo(value)
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

    if spec.freq == "MINUTELY":
        candidate = local_after.replace(microsecond=0)
        if candidate <= local_after:
            candidate += timedelta(minutes=1)
        return candidate.astimezone(UTC)

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
