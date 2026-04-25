from vesperaflow_core.temporal_ids import (
    temporal_schedule_id,
    workflow_id_for_occurrence,
    workflow_id_for_run,
)


def test_temporal_schedule_id_uses_product_schedule_id() -> None:
    assert temporal_schedule_id("sch_123") == "vesperaflow.schedule.sch_123"


def test_workflow_id_for_run_uses_product_run_id() -> None:
    assert workflow_id_for_run("run_123") == "vesperaflow.run.run_123"


def test_workflow_id_for_occurrence_uses_schedule_id_and_occurrence_key() -> None:
    assert (
        workflow_id_for_occurrence("sch_123", "20260429T010000Z")
        == "vesperaflow.occurrence.sch_123.20260429T010000Z"
    )
