"""EMR resource-tag AWS operation family.

Official API: https://docs.aws.amazon.com/emr/latest/APIReference/API_AddTags.html
"""

from __future__ import annotations

from mystack.aws_protocol import OperationFamily
from mystack.emr.application.use_cases import EmrClusterCommands

from .aws_errors import emr_family
from .aws_shapes import resource_id, tag


class TagOperationFamily:
    def __init__(self, commands: EmrClusterCommands) -> None:
        self._commands = commands

    def family(self) -> OperationFamily:
        return emr_family(
            "tag",
            {
                "AddTags": self.add_tags,
                "RemoveTags": self.remove_tags,
            },
        )

    async def add_tags(self, payload, context):
        del context
        await self._commands.add_tags(
            resource_id(payload), dict(tag(value) for value in payload["Tags"])
        )
        return {}

    async def remove_tags(self, payload, context):
        del context
        await self._commands.remove_tags(resource_id(payload), map(str, payload["TagKeys"]))
        return {}
