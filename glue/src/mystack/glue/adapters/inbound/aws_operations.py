"""Reviewed Mystack Glue Data Catalog operation inventory.

Official inventory source:
https://github.com/boto/botocore/tree/develop/botocore/data/glue
"""

IMPLEMENTED_GLUE_OPERATIONS = frozenset(
    {
        "BatchCreatePartition",
        "BatchDeletePartition",
        "BatchGetPartition",
        "BatchGetTableOptimizer",
        "BatchUpdatePartition",
        "CreateDatabase",
        "CreatePartition",
        "CreateTable",
        "CreateTableOptimizer",
        "DeleteDatabase",
        "DeletePartition",
        "DeleteTable",
        "DeleteTableOptimizer",
        "GetCatalogImportStatus",
        "GetDatabase",
        "GetDatabases",
        "GetPartition",
        "GetPartitions",
        "GetTable",
        "GetTableOptimizer",
        "GetTables",
        "GetTableVersion",
        "GetTableVersions",
        "ListTableOptimizerRuns",
        "UpdateDatabase",
        "UpdatePartition",
        "UpdateTable",
        "UpdateTableOptimizer",
    }
)
