"""AWS JSON 1.1 inbound EMR adapter.

Protocol reference: https://docs.aws.amazon.com/emr/latest/APIReference/Welcome.html
"""

from .aws import EmrAwsAdapter
from .management import EmrManagementAdapter

__all__ = ["EmrAwsAdapter", "EmrManagementAdapter"]
