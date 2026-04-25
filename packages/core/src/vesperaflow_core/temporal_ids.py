"""Temporal identifier conventions."""


def temporal_schedule_id(schedule_id: str) -> str:
    return f"vesperaflow.schedule.{schedule_id}"


def workflow_id_for_run(run_id: str) -> str:
    return f"vesperaflow.run.{run_id}"


def workflow_id_for_occurrence(schedule_id: str, occurrence_key: str) -> str:
    return f"vesperaflow.occurrence.{schedule_id}.{occurrence_key}"

