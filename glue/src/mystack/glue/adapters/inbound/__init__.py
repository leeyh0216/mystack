"""AWS JSON 1.1 Glue inbound adapter.

Protocol reference: https://docs.aws.amazon.com/glue/latest/webapi/Welcome.html
"""

from mystack.glue.adapters.inbound.aws import GlueAwsAdapter
from mystack.glue.adapters.inbound.management import GlueManagementAdapter

__all__ = ["GlueAwsAdapter", "GlueManagementAdapter"]
