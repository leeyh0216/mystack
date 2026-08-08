"""Glue domain failures; AWS error codes are assigned only by the inbound adapter.

Reference: https://docs.aws.amazon.com/glue/latest/dg/aws-glue-api-exceptions.html
"""


class GlueDomainError(Exception):
    pass


class AlreadyExistsError(GlueDomainError):
    pass


class EntityNotFoundError(GlueDomainError):
    pass


class InvalidInputError(GlueDomainError):
    pass


class VersionMismatchError(GlueDomainError):
    pass
