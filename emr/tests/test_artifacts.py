"""Spark submit artifact materialization derived from official submission options.

https://spark.apache.org/docs/3.5.4/submitting-applications.html
"""

from __future__ import annotations

from pathlib import Path

import pytest
from mystack.emr.adapters.outbound.runtime import SparkSubmitArtifactMaterializer


class _Artifacts:
    def __init__(self) -> None:
        self.requests: list[tuple[str, Path]] = []

    async def materialize(self, uri: str, destination: Path) -> Path:
        self.requests.append((uri, destination))
        return destination / Path(uri.split("#", 1)[0]).name


@pytest.mark.asyncio
async def test_materializes_primary_and_comma_separated_dependency_resources(
    tmp_path: Path,
) -> None:
    artifacts = _Artifacts()
    materializer = SparkSubmitArtifactMaterializer(artifacts)

    result = await materializer.materialize(
        [
            "--py-files",
            "s3://assets/one.zip,s3a://assets/two.zip",
            "--files=s3://assets/settings.json#settings",
            "s3://assets/job.py",
            "argument",
        ],
        work_dir=tmp_path,
        option_value_names=frozenset({"--py-files", "--files"}),
    )

    assert result == [
        "--py-files",
        (f"{tmp_path}/dependencies/py-files/0/one.zip,{tmp_path}/dependencies/py-files/1/two.zip"),
        f"--files={tmp_path}/dependencies/files/0/settings.json#settings",
        f"{tmp_path}/application/job.py",
        "argument",
    ]
    assert [uri for uri, _ in artifacts.requests] == [
        "s3://assets/one.zip",
        "s3a://assets/two.zip",
        "s3://assets/settings.json#settings",
        "s3://assets/job.py",
    ]


@pytest.mark.asyncio
async def test_preserves_local_resources_and_rejects_missing_option_value(tmp_path: Path) -> None:
    artifacts = _Artifacts()
    materializer = SparkSubmitArtifactMaterializer(artifacts)

    result = await materializer.materialize(
        ["--jars", "/opt/app/dependency.jar", "/opt/app/job.jar"],
        work_dir=tmp_path,
        option_value_names=frozenset({"--jars"}),
    )

    assert result == ["--jars", "/opt/app/dependency.jar", "/opt/app/job.jar"]
    assert artifacts.requests == []

    with pytest.raises(ValueError, match="--archives requires a value"):
        await materializer.materialize(
            ["--archives"],
            work_dir=tmp_path,
            option_value_names=frozenset({"--archives"}),
        )
