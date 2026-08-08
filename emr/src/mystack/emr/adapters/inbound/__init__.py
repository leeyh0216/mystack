"""AWS JSON 1.1 inbound EMR adapter.

Protocol reference: https://docs.aws.amazon.com/emr/latest/APIReference/Welcome.html
"""

from mystack.emr.adapters.inbound.aws import EmrAwsAdapter
from mystack.emr.adapters.inbound.log_stream import EmrLogEventStream
from mystack.emr.adapters.inbound.management import EmrManagementAdapter
from mystack.emr.adapters.inbound.startup import (
    StartupClusterPlan,
    StartupClusterProvisioner,
    load_startup_cluster_plan,
)

__all__ = [
    "EmrAwsAdapter",
    "EmrLogEventStream",
    "EmrManagementAdapter",
    "StartupClusterPlan",
    "StartupClusterProvisioner",
    "load_startup_cluster_plan",
]
