"""Public, versioned Glue extension SPIs.

Python entry-point discovery:
https://docs.python.org/3/library/importlib.metadata.html#entry-points
"""

from ._common import GlueExtensionIdentity
from .application import GlueApplicationContextV1, GlueApplicationExtensionProviderV1
from .stable import (
    CatalogDatabaseSnapshot,
    CatalogPartitionSnapshot,
    CatalogTableSnapshot,
    CatalogTableVersionSnapshot,
    GlueCatalogCapabilitiesV1,
    GlueStableContextV1,
    GlueStableExtensionProviderV1,
)
from .unsafe import GlueUnsafeContextV1, GlueUnsafeExtensionProviderV1

__all__ = [
    "CatalogDatabaseSnapshot",
    "CatalogPartitionSnapshot",
    "CatalogTableSnapshot",
    "CatalogTableVersionSnapshot",
    "GlueApplicationContextV1",
    "GlueApplicationExtensionProviderV1",
    "GlueCatalogCapabilitiesV1",
    "GlueExtensionIdentity",
    "GlueStableContextV1",
    "GlueStableExtensionProviderV1",
    "GlueUnsafeContextV1",
    "GlueUnsafeExtensionProviderV1",
]
