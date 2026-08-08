"""Reviewed Mystack EMR operation inventory.

Official inventory source:
https://github.com/boto/botocore/tree/develop/botocore/data/emr
"""

IMPLEMENTED_EMR_OPERATIONS = frozenset(
    {
        "AddJobFlowSteps",
        "AddTags",
        "CancelSteps",
        "DescribeCluster",
        "DescribeStep",
        "ListBootstrapActions",
        "ListClusters",
        "ListSteps",
        "RemoveTags",
        "RunJobFlow",
        "SetTerminationProtection",
        "SetVisibleToAllUsers",
        "TerminateJobFlows",
    }
)
