"""Reviewed Mystack Glue Data Catalog operation inventory.

Official inventory source:
https://github.com/boto/botocore/tree/develop/botocore/data/glue
"""

IMPLEMENTED_GLUE_OPERATIONS = frozenset(
    {
        "BatchCreatePartition",
        "BatchDeletePartition",
        "BatchGetPartition",
        "BatchUpdatePartition",
        "CreateDatabase",
        "CreatePartition",
        "CreateTable",
        "DeleteDatabase",
        "DeletePartition",
        "DeleteTable",
        "GetCatalogImportStatus",
        "GetDatabase",
        "GetDatabases",
        "GetPartition",
        "GetPartitions",
        "GetTable",
        "GetTables",
        "GetTableVersion",
        "GetTableVersions",
        "UpdateDatabase",
        "UpdatePartition",
        "UpdateTable",
    }
)
