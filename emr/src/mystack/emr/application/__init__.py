"""EMR application use cases.

Reference: https://docs.aws.amazon.com/prescriptive-guidance/latest/hexagonal-architectures/overview.html
"""

from mystack.emr.application.policy import EmrPolicy, ReleaseProfile
from mystack.emr.application.service import EmrApplication

__all__ = ["EmrApplication", "EmrPolicy", "ReleaseProfile"]
