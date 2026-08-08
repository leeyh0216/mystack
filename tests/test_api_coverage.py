"""Coverage-baseline drift reporting contracts.

Official model source:
https://github.com/boto/botocore/tree/develop/botocore/data
"""

from __future__ import annotations

import copy

from scripts.api_coverage import compare, create_baseline
from scripts.model_manifest import create_manifest


def test_reports_added_removed_and_changed_operations() -> None:
    manifest = create_manifest()
    baseline = create_baseline(manifest)
    changed = copy.deepcopy(manifest)
    emr = changed["services"]["emr"]["operation_fingerprints"]
    glue = changed["services"]["glue"]["operation_fingerprints"]
    emr["NewUpstreamOperation"] = "new-fingerprint"
    emr["RunJobFlow"] = "changed-fingerprint"
    del glue["GetDatabase"]

    report = compare(baseline, changed)

    assert report["services"]["emr"]["operations_added_unclassified"] == ["NewUpstreamOperation"]
    assert report["services"]["emr"]["operations_changed"] == ["RunJobFlow"]
    assert report["services"]["glue"]["operations_removed"] == ["GetDatabase"]
