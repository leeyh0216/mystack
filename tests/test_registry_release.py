"""OCI/Trivy release evidence derived from official specifications.

https://github.com/opencontainers/image-spec/blob/main/image-index.md
https://trivy.dev/docs/latest/guide/references/configuration/cli/trivy_image/
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest
import yaml

from scripts.release.registry_release import (
    ReleaseContractError,
    ReleaseGate,
    VulnerabilityExceptionPolicy,
    check_config,
    evaluate_scans,
    load_config,
    resolve_publication_plan,
    summarize_trivy,
    verify_index,
)

ROOT = Path(__file__).parents[1]


def image_index(*platforms: str) -> dict[str, object]:
    manifests = []
    for index, platform in enumerate(platforms):
        os_name, architecture = platform.split("/")
        manifests.append(
            {
                "mediaType": "application/vnd.oci.image.manifest.v1+json",
                "digest": f"sha256:{index:064x}",
                "platform": {"os": os_name, "architecture": architecture},
            }
        )
    manifests.append(
        {
            "mediaType": "application/vnd.oci.image.manifest.v1+json",
            "digest": "sha256:" + "f" * 64,
            "platform": {"os": "unknown", "architecture": "unknown"},
        }
    )
    return {
        "schemaVersion": 2,
        "mediaType": "application/vnd.oci.image.index.v1+json",
        "manifests": manifests,
    }


def test_verify_index_requires_every_runtime_platform_and_ignores_attestations() -> None:
    result = verify_index(image_index("linux/amd64", "linux/arm64"), ["linux/amd64", "linux/arm64"])

    assert [item["platform"] for item in result] == ["linux/amd64", "linux/arm64"]


def test_verify_index_reports_missing_platform() -> None:
    with pytest.raises(ReleaseContractError, match="linux/arm64"):
        verify_index(image_index("linux/amd64"), ["linux/amd64", "linux/arm64"])


def test_verify_index_rejects_a_single_platform_manifest() -> None:
    with pytest.raises(ReleaseContractError, match="mediaType"):
        verify_index(
            {
                "schemaVersion": 2,
                "mediaType": "application/vnd.oci.image.manifest.v1+json",
                "manifests": [],
            },
            ["linux/amd64"],
        )


def test_trivy_summary_handles_missing_and_multiple_result_sections() -> None:
    report = {
        "Results": [
            {"Vulnerabilities": [{"Severity": "HIGH"}, {"Severity": "CRITICAL"}]},
            {"Vulnerabilities": None},
            {"Vulnerabilities": [{"Severity": "high"}]},
        ]
    }

    assert summarize_trivy(report) == {"HIGH": 2, "CRITICAL": 1}


def test_scan_policy_evaluates_all_platforms_before_rejecting() -> None:
    with pytest.raises(ReleaseContractError, match="linux/arm64:CRITICAL=1"):
        evaluate_scans(
            [
                ("linux/amd64", {"Results": []}),
                (
                    "linux/arm64",
                    {"Results": [{"Vulnerabilities": [{"Severity": "CRITICAL"}]}]},
                ),
            ],
            ["CRITICAL"],
        )


def test_scan_policy_returns_auditable_counts() -> None:
    result = evaluate_scans(
        [
            (
                "linux/amd64",
                {"Results": [{"Vulnerabilities": [{"Severity": "LOW"}]}]},
            ),
            ("linux/arm64", {"Results": []}),
        ],
        ["CRITICAL"],
    )

    assert result["passed"] is True
    assert result["platforms"][0]["severity_counts"] == {"LOW": 1}
    assert result["platforms"][0]["raw_severity_counts"] == {"LOW": 1}
    assert result["platforms"][0]["suppressed"] == []


def test_scan_exception_requires_an_exact_coordinate_and_records_raw_counts() -> None:
    config = load_config(ROOT / "config/release/registry-release.json")
    policy = VulnerabilityExceptionPolicy.from_config(
        config,
        component="emr",
        evaluation_date=date(2026, 8, 9),
    )
    report = {
        "Results": [
            {
                "Vulnerabilities": [
                    {
                        "VulnerabilityID": "CVE-2022-46337",
                        "PkgName": "org.apache.derby:derby",
                        "InstalledVersion": "10.14.2.0",
                        "PkgPath": "opt/spark/jars/derby-10.14.2.0.jar",
                        "Severity": "CRITICAL",
                    }
                ]
            }
        ]
    }

    result = evaluate_scans([("linux/amd64", report)], ["CRITICAL"], policy)

    platform = result["platforms"][0]
    assert platform["raw_severity_counts"] == {"CRITICAL": 1}
    assert platform["severity_counts"] == {}
    assert platform["suppressed"][0]["id"] == "CVE-2022-46337"
    assert platform["suppressed"][0]["expires_on"] == "2026-11-09"


@pytest.mark.parametrize(
    ("component", "path", "evaluation_date"),
    [
        ("proxy", "opt/spark/jars/derby-10.14.2.0.jar", date(2026, 8, 9)),
        ("emr", "opt/spark/jars/another-derby.jar", date(2026, 8, 9)),
        ("emr", "opt/spark/jars/derby-10.14.2.0.jar", date(2026, 11, 10)),
    ],
)
def test_scan_exception_cannot_cross_component_path_or_expiration(
    component: str,
    path: str,
    evaluation_date: date,
) -> None:
    config = load_config(ROOT / "config/release/registry-release.json")
    policy = VulnerabilityExceptionPolicy.from_config(
        config,
        component=component,
        evaluation_date=evaluation_date,
    )
    report = {
        "Results": [
            {
                "Vulnerabilities": [
                    {
                        "VulnerabilityID": "CVE-2022-46337",
                        "PkgName": "org.apache.derby:derby",
                        "InstalledVersion": "10.14.2.0",
                        "PkgPath": path,
                        "Severity": "CRITICAL",
                    }
                ]
            }
        ]
    }

    with pytest.raises(ReleaseContractError, match="CRITICAL=1"):
        evaluate_scans([("linux/amd64", report)], ["CRITICAL"], policy)


def test_committed_release_config_references_real_builds_and_official_sources() -> None:
    config = load_config(ROOT / "config/release/registry-release.json")

    report = check_config(config, ROOT)

    assert report["registry"] == "ghcr.io"
    assert report["consumer_visibility"] == "public"
    assert report["components"] == ["proxy", "emr", "glue"]
    assert all((ROOT / item["dockerfile"]).is_file() for item in config["components"])
    serialized = json.dumps(config)
    assert "docs.github.com" in serialized
    assert "opencontainers/image-spec" in serialized
    assert config["preflight_timeout_minutes"] == 60
    assert config["tags"]["snapshot_retention_days"] == 30
    assert config["tags"]["publish_latest"] is False
    assert len(config["scan"]["exceptions"]) == 13
    assert all(exception["references"] for exception in config["scan"]["exceptions"])


def test_publication_plan_compiles_every_component_platform_without_shell_logic() -> None:
    config = load_config(ROOT / "config/release/registry-release.json")

    plan = resolve_publication_plan(config)

    assert [item["name"] for item in plan["component_matrix"]["include"]] == [
        "proxy",
        "emr",
        "glue",
    ]
    assert len(plan["preflight_matrix"]["include"]) == 6
    assert {item["platform_slug"] for item in plan["preflight_matrix"]["include"]} == {
        "linux-amd64",
        "linux-arm64",
    }


def test_release_config_rejects_non_public_consumer_visibility() -> None:
    config = load_config(ROOT / "config/release/registry-release.json")
    config["consumer_visibility"] = "private"

    with pytest.raises(ReleaseContractError, match="consumer_visibility"):
        check_config(config, ROOT)


def _write_complete_preflight(
    root: Path,
    config: dict,
    *,
    source_sha: str = "a" * 40,
    version: str = "v1.2.3",
) -> None:
    gate = ReleaseGate(config)
    for index, component in enumerate(config["components"]):
        for platform_index, platform in enumerate(config["platforms"]):
            report = gate.record(
                component=component["name"],
                platform=platform,
                image_id=f"sha256:{index * 10 + platform_index:064x}",
                source_sha=source_sha,
                version=version,
                scan_report={"Results": []},
            )
            destination = (
                root
                / "preflight"
                / component["name"]
                / platform.replace("/", "-")
                / "preflight.json"
            )
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(json.dumps(report), encoding="utf-8")


def test_aggregate_gate_requires_and_authorizes_every_local_build_scan(tmp_path: Path) -> None:
    config = load_config(ROOT / "config/release/registry-release.json")
    _write_complete_preflight(tmp_path, config)
    gate = ReleaseGate(config)

    report = gate.verify(
        evidence_root=tmp_path,
        selection="all",
        source_sha="a" * 40,
        version="v1.2.3",
    )
    authorization = gate.authorize(
        report,
        selection="all",
        source_sha="a" * 40,
        version="v1.2.3",
    )

    assert report["authorized"] is True
    assert len(report["records"]) == 6
    assert len(report["authorization_sha256"]) == 64
    assert authorization["components"] == ["proxy", "emr", "glue"]


def test_aggregate_gate_rejects_missing_tampered_and_replayed_evidence(tmp_path: Path) -> None:
    config = load_config(ROOT / "config/release/registry-release.json")
    _write_complete_preflight(tmp_path, config)
    gate = ReleaseGate(config)
    missing = tmp_path / "preflight/glue/linux-arm64/preflight.json"
    missing.unlink()
    with pytest.raises(ReleaseContractError, match="missing or invalid preflight"):
        gate.verify(
            evidence_root=tmp_path,
            selection="all",
            source_sha="a" * 40,
            version="v1.2.3",
        )

    _write_complete_preflight(tmp_path, config)
    tampered_path = tmp_path / "preflight/proxy/linux-amd64/preflight.json"
    tampered = json.loads(tampered_path.read_text(encoding="utf-8"))
    tampered["scan"]["passed"] = False
    tampered_path.write_text(json.dumps(tampered), encoding="utf-8")
    with pytest.raises(ReleaseContractError, match="context mismatch"):
        gate.verify(
            evidence_root=tmp_path,
            selection="all",
            source_sha="a" * 40,
            version="v1.2.3",
        )

    _write_complete_preflight(tmp_path, config)
    valid = gate.verify(
        evidence_root=tmp_path,
        selection="all",
        source_sha="a" * 40,
        version="v1.2.3",
    )
    with pytest.raises(ReleaseContractError, match="authorization context mismatch"):
        gate.authorize(
            valid,
            selection="all",
            source_sha="b" * 40,
            version="v1.2.3",
        )


def test_preflight_policy_failure_cannot_create_evidence() -> None:
    config = load_config(ROOT / "config/release/registry-release.json")
    gate = ReleaseGate(config)
    with pytest.raises(ReleaseContractError, match="CRITICAL=1"):
        gate.record(
            component="proxy",
            platform="linux/amd64",
            image_id="sha256:" + "1" * 64,
            source_sha="a" * 40,
            version="v1.2.3",
            scan_report={"Results": [{"Vulnerabilities": [{"Severity": "CRITICAL"}]}]},
        )


def _workflow(path: str) -> dict:
    return yaml.load((ROOT / path).read_text(encoding="utf-8"), Loader=yaml.BaseLoader)


def test_publication_workflow_is_reusable_only_and_write_permission_is_final() -> None:
    workflow = _workflow(".github/workflows/container-publish.yml")
    assert set(workflow["on"]) == {"workflow_call"}
    assert workflow["permissions"] == {"actions": "read", "contents": "read"}
    assert set(workflow["on"]["workflow_call"]["inputs"]) >= {
        "channel",
        "ci_run_id",
        "source_sha",
    }

    jobs = workflow["jobs"]
    package_writers = [
        name for name, job in jobs.items() if job.get("permissions", {}).get("packages") == "write"
    ]
    assert package_writers == ["publish"]
    content_writers = [
        name for name, job in jobs.items() if job.get("permissions", {}).get("contents") == "write"
    ]
    assert content_writers == ["ensure-stable-tag", "finalize-stable-release"]
    assert set(jobs["aggregate-gate"]["needs"]) == {
        "prepare",
        "required-validation",
        "local-build-scan",
    }
    assert set(jobs["publish"]["needs"]) == {
        "prepare",
        "aggregate-gate",
        "ensure-stable-tag",
    }
    assert jobs["aggregate-gate"]["if"] == "${{ success() }}"
    assert "ensure-stable-tag.result" in jobs["publish"]["if"]


def test_only_final_job_can_mutate_registry_and_preflight_is_local() -> None:
    jobs = _workflow(".github/workflows/container-publish.yml")["jobs"]
    preflight = json.dumps(jobs["local-build-scan"], sort_keys=True)
    publish = json.dumps(jobs["publish"], sort_keys=True)

    assert "docker/login-action" not in preflight
    assert '"push": "false"' in preflight
    assert '"load": "true"' in preflight
    assert "record-preflight" in preflight
    assert "verify_glue_sqlite_runtime.py" in preflight
    assert "Verify the source-built Glue SQLite runtime" in preflight
    assert "docker/login-action" in publish
    assert '"push": "true"' in publish
    assert "authorize-publication" in publish
    assert publish.index("authorize-publication") < publish.index("docker/login-action")
    assert "-m scripts.release.release_policy binding" in publish
    assert "steps.identity.outputs.exists != 'true'" in publish


def test_publication_reprobes_each_published_glue_platform_digest_before_release() -> None:
    jobs = _workflow(".github/workflows/container-publish.yml")["jobs"]
    verification_steps = jobs["verify-publication"]["steps"]
    publication_verification = json.dumps(verification_steps, sort_keys=True)
    runtime_probe = next(
        step
        for step in verification_steps
        if step.get("name")
        == "Prove every exact tag is anonymously readable, source-bound, and runtime-verified"
    )
    evidence_upload = next(
        step
        for step in verification_steps
        if step.get("name") == "Upload anonymous index, SQLite runtime, and retention evidence"
    )

    assert "docker/setup-qemu-action" in publication_verification
    assert "verify_glue_sqlite_runtime.py" in publication_verification
    assert "platform_digest=$(jq -er" in runtime_probe["run"]
    assert '--image "$image@$platform_digest"' in runtime_probe["run"]
    assert "PREFLIGHT_TIMEOUT_MINUTES" in runtime_probe["run"]
    assert "sqlite-runtime.json" in runtime_probe["run"]
    assert evidence_upload["if"] == "always()"
    assert evidence_upload["with"]["retention-days"] == "14"
    assert jobs["finalize-stable-release"]["needs"] == ["prepare", "verify-publication"]


def test_release_entrypoint_only_calls_the_reusable_pipeline() -> None:
    workflow = _workflow(".github/workflows/release.yml")
    assert set(workflow["on"]) == {"workflow_run"}
    assert set(workflow["jobs"]) == {"plan", "publish"}
    trigger = workflow["on"]["workflow_run"]
    assert trigger["workflows"] == ["CI"]
    assert set(trigger["branches"]) == {"main", "develop"}
    publish = workflow["jobs"]["publish"]
    assert publish["uses"] == "./.github/workflows/container-publish.yml"
    assert publish["permissions"] == {"contents": "write", "packages": "write"}
    assert publish["with"]["ci_run_id"] == "${{ github.event.workflow_run.id }}"
    assert "pull_request" not in json.dumps(workflow["on"])


def test_prepare_version_pr_can_change_git_but_never_packages_or_releases() -> None:
    workflow = _workflow(".github/workflows/prepare-version-pr.yml")

    assert set(workflow["on"]) == {"workflow_dispatch"}
    job = workflow["jobs"]["prepare"]
    assert job["permissions"] == {"contents": "write", "pull-requests": "write"}
    serialized = json.dumps(job, sort_keys=True)
    assert "version.py" in serialized
    assert "gh pr create" in serialized
    assert "packages" not in serialized
    assert "gh release" not in serialized
    assert "docker" not in serialized
