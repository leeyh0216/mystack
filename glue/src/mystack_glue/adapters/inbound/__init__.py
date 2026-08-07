"""AWS JSON 1.1 Glue inbound adapter.

Protocol reference: https://docs.aws.amazon.com/glue/latest/webapi/Welcome.html
"""

from .aws import GlueAwsAdapter

__all__ = ["GlueAwsAdapter"]
