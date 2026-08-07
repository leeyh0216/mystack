"""Declarative AWS service route detection tests.

References:
- https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_sigv.html
- https://github.com/boto/botocore/tree/develop/botocore/data
"""

from mystack_proxy.config import ServiceRoute
from mystack_proxy.routing import AwsServiceDetector


def detector() -> AwsServiceDetector:
    return AwsServiceDetector(
        (
            ServiceRoute(
                name="emr",
                backend_url="http://emr:8080",
                target_prefixes=("ElasticMapReduce",),
                signing_names=("elasticmapreduce",),
                host_prefixes=("elasticmapreduce", "emr"),
            ),
            ServiceRoute(
                name="glue",
                backend_url="http://glue:8080",
                target_prefixes=("AWSGlue",),
                signing_names=("glue",),
                host_prefixes=("glue",),
            ),
        )
    )


def test_detects_target_prefix_before_other_evidence() -> None:
    match = detector().detect(
        {
            "X-Amz-Target": "AWSGlue.GetTable",
            "Authorization": (
                "AWS4-HMAC-SHA256 Credential=test/20260808/us-east-1/s3/aws4_request"
            ),
        }
    )
    assert match.route is not None
    assert match.route.name == "glue"
    assert match.evidence == "x-amz-target"


def test_detects_emr_from_sigv4_scope() -> None:
    match = detector().detect(
        {
            "Authorization": (
                "AWS4-HMAC-SHA256 Credential=test/20260808/ap-northeast-2/"
                "elasticmapreduce/aws4_request, SignedHeaders=host, Signature=0"
            )
        }
    )
    assert match.route is not None
    assert match.route.name == "emr"


def test_unknown_service_falls_back_to_localstack() -> None:
    match = detector().detect({"Host": "localhost:4566"})
    assert match.route is None
    assert match.evidence == "fallback"


def test_detects_a_new_emulator_from_configuration_only() -> None:
    custom = ServiceRoute(
        name="athena",
        backend_url="http://athena:8080",
        target_prefixes=("AmazonAthena",),
        signing_names=("athena",),
        host_prefixes=("athena",),
    )
    match = AwsServiceDetector((custom,)).detect(
        {"X-Amz-Target": "AmazonAthena.StartQueryExecution"}
    )
    assert match.route == custom
