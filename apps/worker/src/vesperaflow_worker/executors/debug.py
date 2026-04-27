"""Debug executor adapter."""

import logging
from typing import override

from vesperaflow_core import ExecutionSnapshot, ExecutorOutcome, RunStatus

from .base import ExecutorAdapter

logger = logging.getLogger(__name__)


class DebugPrinterExecutor(ExecutorAdapter):
    @override
    async def execute(self, snapshot: ExecutionSnapshot) -> ExecutorOutcome:
        logger.info("debug_printer_snapshot %s", snapshot.model_dump_json())
        return ExecutorOutcome(
            terminal_status=RunStatus.COMPLETED,
            result_summary=(
                f"Debug printer completed run {snapshot.run_id} "
                f"for task {snapshot.task_id}."
            ),
            terminal_code="debug_printer_completed",
        )
