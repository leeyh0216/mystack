"""Reusable typed profiles for compatibility tests.

Adding a client/runtime version starts here and at the test that proves it.  The collection
compiler validates these declared versions against the retained legacy manifest during the
transition, so this module does not silently create a version cross-product.
"""

from __future__ import annotations

from tests.support.compatibility import CompatibilityProfile, ExecutionKind, Lane

_BOTOCORE_MODEL = "https://github.com/boto/botocore/tree/develop/botocore/data"
_EMR_RELEASE = "https://docs.aws.amazon.com/emr/latest/ReleaseGuide/emr-780-release.html"
_GLUE_RELEASE = "https://docs.aws.amazon.com/glue/latest/dg/migrating-version-50.html"
_AWS_SDK_PANDAS = "https://aws-sdk-pandas.readthedocs.io/en/stable/api.html"
_GLUE_HIVE = "https://docs.aws.amazon.com/glue/latest/dg/aws-glue-programming-etl-glue-data-catalog-hive.html"
_GLUE_ICEBERG = (
    "https://docs.aws.amazon.com/glue/latest/dg/aws-glue-programming-etl-format-iceberg.html"
)

BOTO3_BOTOCORE_CONTRACT = CompatibilityProfile(
    id="boto3-botocore-1.43.66-contract",
    title_en="boto3 and botocore control-plane contracts",
    title_ko="boto3와 botocore control plane 계약",
    client="boto3",
    versions={"boto3": "1.43.66", "botocore": "1.43.66"},
    runtime_profile="python-3.11",
    runtime_kind="python",
    python_version="3.11",
    lane=Lane.REQUIRED,
    execution=ExecutionKind.CONTRACT,
    expected_duration_minutes=15,
    reference_urls=(_BOTOCORE_MODEL,),
)

BOTO3_BOTOCORE_PUBLIC_PROXY = CompatibilityProfile(
    id="boto3-botocore-1.43.66-public-proxy",
    title_en="boto3 Glue operations through the public Proxy",
    title_ko="공개 Proxy를 통과하는 boto3 Glue operation",
    client="boto3",
    versions={"boto3": "1.43.66", "botocore": "1.43.66"},
    runtime_profile="glue-5.0-spark-3.5.4",
    runtime_kind="glue",
    python_version="3.11",
    lane=Lane.REQUIRED,
    execution=ExecutionKind.E2E,
    expected_duration_minutes=60,
    reference_urls=(_BOTOCORE_MODEL,),
)

AWSWRANGLER_GLUE_S3 = CompatibilityProfile(
    id="awswrangler-3.17.0-glue-s3",
    title_en="AWS SDK for pandas Glue and S3 round trip",
    title_ko="AWS SDK for pandas Glue와 S3 왕복",
    client="awswrangler",
    versions={"awswrangler": "3.17.0", "boto3": "1.43.66", "botocore": "1.43.66"},
    runtime_profile="glue-5.0-spark-3.5.4",
    runtime_kind="glue",
    python_version="3.11",
    lane=Lane.REQUIRED,
    execution=ExecutionKind.E2E,
    expected_duration_minutes=60,
    reference_urls=(_AWS_SDK_PANDAS, _BOTOCORE_MODEL),
)

EMR_LOCAL_SPARK = CompatibilityProfile(
    id="emr-7.8.0-spark-3.5.4",
    title_en="EMR bootstrap and real local Spark step",
    title_ko="EMR bootstrap과 실제 local Spark step",
    client="boto3-and-spark-submit",
    versions={"boto3": "1.43.66", "botocore": "1.43.66", "emr": "7.8.0", "spark": "3.5.4"},
    runtime_profile="emr-7.8.0-spark-3.5.4",
    runtime_kind="emr",
    python_version="3.11",
    lane=Lane.REQUIRED,
    execution=ExecutionKind.E2E,
    expected_duration_minutes=60,
    reference_urls=(_EMR_RELEASE, _BOTOCORE_MODEL),
)

GLUE_SPARK_HIVE_ICEBERG = CompatibilityProfile(
    id="glue-5.0-spark-3.5.4-hive-iceberg-1.7.1",
    title_en="Glue Spark Hive and Iceberg catalogs",
    title_ko="Glue Spark Hive와 Iceberg catalog",
    client="spark-glue-catalog",
    versions={
        "boto3": "1.43.66",
        "botocore": "1.43.66",
        "glue": "5.0",
        "iceberg": "1.7.1",
        "spark": "3.5.4",
    },
    runtime_profile="glue-5.0-spark-3.5.4",
    runtime_kind="glue",
    python_version="3.11",
    lane=Lane.REQUIRED,
    execution=ExecutionKind.E2E,
    expected_duration_minutes=60,
    reference_urls=(_GLUE_RELEASE, _GLUE_HIVE, _GLUE_ICEBERG, _BOTOCORE_MODEL),
)
