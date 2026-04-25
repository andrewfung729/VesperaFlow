"""Temporal identifier conventions."""

import re

_OCCURRENCE_KEY_RE = re.compile(r"^\d{8}T\d{6}Z$")


def temporal_schedule_id(schedule_id: str) -> str:
    return f"vesperaflow.schedule.{schedule_id}"


def workflow_id_for_run(run_id: str) -> str:
    return f"vesperaflow.run.{run_id}"


def workflow_id_for_occurrence(schedule_id: str, occurrence_key: str) -> str:
    validate_occurrence_key(occurrence_key)
    return f"vesperaflow.occurrence.{schedule_id}.{occurrence_key}"


def validate_occurrence_key(occurrence_key: str) -> None:
    if not _OCCURRENCE_KEY_RE.fullmatch(occurrence_key):
        raise ValueError(
            "occurrence_key must use UTC basic ISO format like 20260429T010000Z"
        )
