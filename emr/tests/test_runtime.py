"""Subprocess race regression tests.

References:
- https://docs.python.org/3/library/asyncio-subprocess.html
- https://docs.aws.amazon.com/emr/latest/APIReference/API_CancelSteps.html
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from mystack.aws_protocol import load_configuration
from mystack.emr.adapters.outbound import LocalProcessExecutor
from mystack.emr.config import EmrSettings


@pytest.mark.asyncio
async def test_cancellation_before_process_registration_is_applied(tmp_path: Path) -> None:
    settings = EmrSettings.from_configuration(load_configuration("config/mystack.yaml"))
    executor = LocalProcessExecutor(settings)

    await executor.cancel("j-race", "s-race")
    outcome = await executor.execute(
        cluster_id="j-race",
        operation_id="s-race",
        command=[sys.executable, "-c", "import time; time.sleep(30)"],
        work_dir=tmp_path,
        timeout_seconds=5,
        environment={},
    )

    assert outcome.exit_code != 0
