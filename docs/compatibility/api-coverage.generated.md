# Generated API compatibility matrix

<!-- toc:start -->
## Contents

- [Summary](#summary)
- [Operations](#operations)
<!-- toc:end -->

This file is generated from annotated pytest evidence and operation inventory; do not edit it directly. The official inventory is the [botocore service model](https://github.com/boto/botocore/tree/develop/botocore/data).

botocore: `1.43.66`

## Summary

| Service | COMPATIBLE | PARTIAL | PROTOCOL_ONLY | NOT_PLANNED | Total |
| --- | ---: | ---: | ---: | ---: | ---: |
| EMR | 13 | 0 | 52 | 0 | 65 |
| GLUE | 28 | 0 | 243 | 28 | 299 |

## Operations

| Service | Operation | Status | Meaning |
| --- | --- | --- | --- |
| EMR | `AddInstanceFleet` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| EMR | `AddInstanceGroups` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| EMR | `AddJobFlowSteps` | `COMPATIBLE` | Implemented with boto3 contracts and public Proxy E2E |
| EMR | `AddTags` | `COMPATIBLE` | Implemented with boto3 contracts and public Proxy E2E |
| EMR | `CancelSteps` | `COMPATIBLE` | Implemented with boto3 contracts and public Proxy E2E |
| EMR | `CreatePersistentAppUI` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| EMR | `CreateSecurityConfiguration` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| EMR | `CreateStudio` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| EMR | `CreateStudioSessionMapping` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| EMR | `DeleteSecurityConfiguration` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| EMR | `DeleteStudio` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| EMR | `DeleteStudioSessionMapping` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| EMR | `DescribeCluster` | `COMPATIBLE` | Implemented with boto3 contracts and public Proxy E2E |
| EMR | `DescribeJobFlows` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| EMR | `DescribeNotebookExecution` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| EMR | `DescribePersistentAppUI` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| EMR | `DescribeReleaseLabel` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| EMR | `DescribeSecurityConfiguration` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| EMR | `DescribeStep` | `COMPATIBLE` | Implemented with boto3 contracts and public Proxy E2E |
| EMR | `DescribeStudio` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| EMR | `GetAutoTerminationPolicy` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| EMR | `GetBlockPublicAccessConfiguration` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| EMR | `GetClusterSessionCredentials` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| EMR | `GetManagedScalingPolicy` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| EMR | `GetOnClusterAppUIPresignedURL` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| EMR | `GetPersistentAppUIPresignedURL` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| EMR | `GetSession` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| EMR | `GetSessionEndpoint` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| EMR | `GetStudioSessionMapping` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| EMR | `ListBootstrapActions` | `COMPATIBLE` | Implemented with boto3 contracts and public Proxy E2E |
| EMR | `ListClusters` | `COMPATIBLE` | Implemented with boto3 contracts and public Proxy E2E |
| EMR | `ListInstanceFleets` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| EMR | `ListInstanceGroups` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| EMR | `ListInstances` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| EMR | `ListNotebookExecutions` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| EMR | `ListReleaseLabels` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| EMR | `ListSecurityConfigurations` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| EMR | `ListSessions` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| EMR | `ListSteps` | `COMPATIBLE` | Implemented with boto3 contracts and public Proxy E2E |
| EMR | `ListStudioSessionMappings` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| EMR | `ListStudios` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| EMR | `ListSupportedInstanceTypes` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| EMR | `ModifyCluster` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| EMR | `ModifyInstanceFleet` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| EMR | `ModifyInstanceGroups` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| EMR | `PutAutoScalingPolicy` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| EMR | `PutAutoTerminationPolicy` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| EMR | `PutBlockPublicAccessConfiguration` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| EMR | `PutManagedScalingPolicy` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| EMR | `RemoveAutoScalingPolicy` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| EMR | `RemoveAutoTerminationPolicy` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| EMR | `RemoveManagedScalingPolicy` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| EMR | `RemoveTags` | `COMPATIBLE` | Implemented with boto3 contracts and public Proxy E2E |
| EMR | `RunJobFlow` | `COMPATIBLE` | Implemented with boto3 contracts and public Proxy E2E |
| EMR | `SetKeepJobFlowAliveWhenNoSteps` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| EMR | `SetTerminationProtection` | `COMPATIBLE` | Implemented with boto3 contracts and public Proxy E2E |
| EMR | `SetUnhealthyNodeReplacement` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| EMR | `SetVisibleToAllUsers` | `COMPATIBLE` | Implemented with boto3 contracts and public Proxy E2E |
| EMR | `StartNotebookExecution` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| EMR | `StartSession` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| EMR | `StopNotebookExecution` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| EMR | `TerminateJobFlows` | `COMPATIBLE` | Implemented with boto3 contracts and public Proxy E2E |
| EMR | `TerminateSession` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| EMR | `UpdateStudio` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| EMR | `UpdateStudioSessionMapping` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `AssociateGlossaryTerms` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `BatchCreatePartition` | `COMPATIBLE` | Implemented with boto3 contracts and public Proxy E2E |
| GLUE | `BatchDeleteConnection` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `BatchDeletePartition` | `COMPATIBLE` | Implemented with boto3 contracts and public Proxy E2E |
| GLUE | `BatchDeleteTable` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `BatchDeleteTableVersion` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `BatchGetBlueprints` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `BatchGetCrawlers` | `NOT_PLANNED` | Glue Job/JobRun/Crawler family excluded |
| GLUE | `BatchGetCustomEntityTypes` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `BatchGetDataQualityResult` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `BatchGetDataQualityRulesetEvaluationRun` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `BatchGetDevEndpoints` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `BatchGetIterableForms` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `BatchGetJobs` | `NOT_PLANNED` | Glue Job/JobRun/Crawler family excluded |
| GLUE | `BatchGetPartition` | `COMPATIBLE` | Implemented with boto3 contracts and public Proxy E2E |
| GLUE | `BatchGetTableOptimizer` | `COMPATIBLE` | Implemented with boto3 contracts and public Proxy E2E |
| GLUE | `BatchGetTriggers` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `BatchGetWorkflows` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `BatchPutDataQualityStatisticAnnotation` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `BatchStopJobRun` | `NOT_PLANNED` | Glue Job/JobRun/Crawler family excluded |
| GLUE | `BatchUpdatePartition` | `COMPATIBLE` | Implemented with boto3 contracts and public Proxy E2E |
| GLUE | `CancelDataQualityRuleRecommendationRun` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `CancelDataQualityRulesetEvaluationRun` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `CancelMLTaskRun` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `CancelStatement` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `CheckSchemaVersionValidity` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `CreateBlueprint` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `CreateCatalog` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `CreateClassifier` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `CreateColumnStatisticsTaskSettings` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `CreateConnection` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `CreateCrawler` | `NOT_PLANNED` | Glue Job/JobRun/Crawler family excluded |
| GLUE | `CreateCustomEntityType` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `CreateDataQualityRuleset` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `CreateDatabase` | `COMPATIBLE` | Implemented with boto3 contracts and public Proxy E2E |
| GLUE | `CreateDevEndpoint` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `CreateGlossary` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `CreateGlossaryTerm` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `CreateGlueIdentityCenterConfiguration` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `CreateIntegration` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `CreateIntegrationResourceProperty` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `CreateIntegrationTableProperties` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `CreateJob` | `NOT_PLANNED` | Glue Job/JobRun/Crawler family excluded |
| GLUE | `CreateMLTransform` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `CreatePartition` | `COMPATIBLE` | Implemented with boto3 contracts and public Proxy E2E |
| GLUE | `CreatePartitionIndex` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `CreateRegistry` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `CreateSchema` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `CreateScript` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `CreateSecurityConfiguration` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `CreateSession` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `CreateTable` | `COMPATIBLE` | Implemented with boto3 contracts and public Proxy E2E |
| GLUE | `CreateTableOptimizer` | `COMPATIBLE` | Implemented with boto3 contracts and public Proxy E2E |
| GLUE | `CreateTrigger` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `CreateUsageProfile` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `CreateUserDefinedFunction` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `CreateWorkflow` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `DeleteAsset` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `DeleteAssetType` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `DeleteAttachment` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `DeleteBlueprint` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `DeleteCatalog` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `DeleteClassifier` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `DeleteColumnStatisticsForPartition` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `DeleteColumnStatisticsForTable` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `DeleteColumnStatisticsTaskSettings` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `DeleteConnection` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `DeleteConnectionType` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `DeleteCrawler` | `NOT_PLANNED` | Glue Job/JobRun/Crawler family excluded |
| GLUE | `DeleteCustomEntityType` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `DeleteDataQualityRuleset` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `DeleteDatabase` | `COMPATIBLE` | Implemented with boto3 contracts and public Proxy E2E |
| GLUE | `DeleteDevEndpoint` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `DeleteFormType` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `DeleteGlossary` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `DeleteGlossaryTerm` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `DeleteGlueIdentityCenterConfiguration` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `DeleteIntegration` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `DeleteIntegrationResourceProperty` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `DeleteIntegrationTableProperties` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `DeleteJob` | `NOT_PLANNED` | Glue Job/JobRun/Crawler family excluded |
| GLUE | `DeleteMLTransform` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `DeletePartition` | `COMPATIBLE` | Implemented with boto3 contracts and public Proxy E2E |
| GLUE | `DeletePartitionIndex` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `DeleteRegistry` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `DeleteResourcePolicy` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `DeleteSchema` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `DeleteSchemaVersions` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `DeleteSecurityConfiguration` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `DeleteSession` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `DeleteTable` | `COMPATIBLE` | Implemented with boto3 contracts and public Proxy E2E |
| GLUE | `DeleteTableOptimizer` | `COMPATIBLE` | Implemented with boto3 contracts and public Proxy E2E |
| GLUE | `DeleteTableVersion` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `DeleteTrigger` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `DeleteUsageProfile` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `DeleteUserDefinedFunction` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `DeleteWorkflow` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `DescribeConnectionType` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `DescribeEntity` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `DescribeInboundIntegrations` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `DescribeIntegrations` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `DisassociateGlossaryTerms` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `GetAsset` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `GetAssetType` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `GetBlueprint` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `GetBlueprintRun` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `GetBlueprintRuns` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `GetCatalog` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `GetCatalogImportStatus` | `COMPATIBLE` | Implemented with boto3 contracts and public Proxy E2E |
| GLUE | `GetCatalogs` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `GetClassifier` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `GetClassifiers` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `GetColumnStatisticsForPartition` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `GetColumnStatisticsForTable` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `GetColumnStatisticsTaskRun` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `GetColumnStatisticsTaskRuns` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `GetColumnStatisticsTaskSettings` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `GetConnection` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `GetConnections` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `GetCrawler` | `NOT_PLANNED` | Glue Job/JobRun/Crawler family excluded |
| GLUE | `GetCrawlerMetrics` | `NOT_PLANNED` | Glue Job/JobRun/Crawler family excluded |
| GLUE | `GetCrawlers` | `NOT_PLANNED` | Glue Job/JobRun/Crawler family excluded |
| GLUE | `GetCustomEntityType` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `GetDashboardUrl` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `GetDataCatalogEncryptionSettings` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `GetDataCatalogExportConfiguration` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `GetDataQualityModel` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `GetDataQualityModelResult` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `GetDataQualityResult` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `GetDataQualityRuleRecommendationRun` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `GetDataQualityRuleset` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `GetDataQualityRulesetEvaluationRun` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `GetDatabase` | `COMPATIBLE` | Implemented with boto3 contracts and public Proxy E2E |
| GLUE | `GetDatabases` | `COMPATIBLE` | Implemented with boto3 contracts and public Proxy E2E |
| GLUE | `GetDataflowGraph` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `GetDevEndpoint` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `GetDevEndpoints` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `GetEntityRecords` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `GetFormType` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `GetGlossary` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `GetGlossaryTerm` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `GetGlueIdentityCenterConfiguration` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `GetIntegrationResourceProperty` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `GetIntegrationTableProperties` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `GetJob` | `NOT_PLANNED` | Glue Job/JobRun/Crawler family excluded |
| GLUE | `GetJobBookmark` | `NOT_PLANNED` | Glue Job/JobRun/Crawler family excluded |
| GLUE | `GetJobRun` | `NOT_PLANNED` | Glue Job/JobRun/Crawler family excluded |
| GLUE | `GetJobRuns` | `NOT_PLANNED` | Glue Job/JobRun/Crawler family excluded |
| GLUE | `GetJobs` | `NOT_PLANNED` | Glue Job/JobRun/Crawler family excluded |
| GLUE | `GetMLTaskRun` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `GetMLTaskRuns` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `GetMLTransform` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `GetMLTransforms` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `GetMapping` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `GetMaterializedViewRefreshTaskRun` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `GetPartition` | `COMPATIBLE` | Implemented with boto3 contracts and public Proxy E2E |
| GLUE | `GetPartitionIndexes` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `GetPartitions` | `COMPATIBLE` | Implemented with boto3 contracts and public Proxy E2E |
| GLUE | `GetPlan` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `GetRegistry` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `GetResourcePolicies` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `GetResourcePolicy` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `GetSchema` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `GetSchemaByDefinition` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `GetSchemaVersion` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `GetSchemaVersionsDiff` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `GetSecurityConfiguration` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `GetSecurityConfigurations` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `GetSession` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `GetSessionEndpoint` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `GetStatement` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `GetTable` | `COMPATIBLE` | Implemented with boto3 contracts and public Proxy E2E |
| GLUE | `GetTableOptimizer` | `COMPATIBLE` | Implemented with boto3 contracts and public Proxy E2E |
| GLUE | `GetTableVersion` | `COMPATIBLE` | Implemented with boto3 contracts and public Proxy E2E |
| GLUE | `GetTableVersions` | `COMPATIBLE` | Implemented with boto3 contracts and public Proxy E2E |
| GLUE | `GetTables` | `COMPATIBLE` | Implemented with boto3 contracts and public Proxy E2E |
| GLUE | `GetTags` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `GetTrigger` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `GetTriggers` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `GetUnfilteredPartitionMetadata` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `GetUnfilteredPartitionsMetadata` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `GetUnfilteredTableMetadata` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `GetUsageProfile` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `GetUserDefinedFunction` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `GetUserDefinedFunctions` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `GetWorkflow` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `GetWorkflowRun` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `GetWorkflowRunProperties` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `GetWorkflowRuns` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `ImportCatalogToGlue` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `ListAssetTypes` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `ListBlueprints` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `ListColumnStatisticsTaskRuns` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `ListConnectionTypes` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `ListCrawlers` | `NOT_PLANNED` | Glue Job/JobRun/Crawler family excluded |
| GLUE | `ListCrawls` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `ListCustomEntityTypes` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `ListDataQualityResults` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `ListDataQualityRuleRecommendationRuns` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `ListDataQualityRulesetEvaluationRuns` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `ListDataQualityRulesets` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `ListDataQualityStatisticAnnotations` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `ListDataQualityStatistics` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `ListDevEndpoints` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `ListEntities` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `ListFormTypes` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `ListGlossaries` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `ListGlossaryTerms` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `ListIntegrationResourceProperties` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `ListIterableForms` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `ListJobs` | `NOT_PLANNED` | Glue Job/JobRun/Crawler family excluded |
| GLUE | `ListMLTransforms` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `ListMaterializedViewRefreshTaskRuns` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `ListRegistries` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `ListSchemaVersions` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `ListSchemas` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `ListSessions` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `ListStatements` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `ListTableOptimizerRuns` | `COMPATIBLE` | Implemented with boto3 contracts and public Proxy E2E |
| GLUE | `ListTriggers` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `ListUsageProfiles` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `ListWorkflows` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `ModifyIntegration` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `PutAsset` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `PutAssetType` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `PutAttachment` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `PutDataCatalogEncryptionSettings` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `PutDataCatalogExportConfiguration` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `PutDataQualityProfileAnnotation` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `PutFormType` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `PutResourcePolicy` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `PutSchemaVersionMetadata` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `PutWorkflowRunProperties` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `QuerySchemaVersionMetadata` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `RegisterConnectionType` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `RegisterSchemaVersion` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `RemoveSchemaVersionMetadata` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `ResetJobBookmark` | `NOT_PLANNED` | Glue Job/JobRun/Crawler family excluded |
| GLUE | `ResumeWorkflowRun` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `RunStatement` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `SearchAssets` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `SearchTables` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `StartBlueprintRun` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `StartColumnStatisticsTaskRun` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `StartColumnStatisticsTaskRunSchedule` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `StartCrawler` | `NOT_PLANNED` | Glue Job/JobRun/Crawler family excluded |
| GLUE | `StartCrawlerSchedule` | `NOT_PLANNED` | Glue Job/JobRun/Crawler family excluded |
| GLUE | `StartDataQualityRuleRecommendationRun` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `StartDataQualityRulesetEvaluationRun` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `StartExportLabelsTaskRun` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `StartImportLabelsTaskRun` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `StartJobRun` | `NOT_PLANNED` | Glue Job/JobRun/Crawler family excluded |
| GLUE | `StartMLEvaluationTaskRun` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `StartMLLabelingSetGenerationTaskRun` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `StartMaterializedViewRefreshTaskRun` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `StartTrigger` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `StartWorkflowRun` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `StopColumnStatisticsTaskRun` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `StopColumnStatisticsTaskRunSchedule` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `StopCrawler` | `NOT_PLANNED` | Glue Job/JobRun/Crawler family excluded |
| GLUE | `StopCrawlerSchedule` | `NOT_PLANNED` | Glue Job/JobRun/Crawler family excluded |
| GLUE | `StopMaterializedViewRefreshTaskRun` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `StopSession` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `StopTrigger` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `StopWorkflowRun` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `TagResource` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `TestConnection` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `UntagResource` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `UpdateAsset` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `UpdateBlueprint` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `UpdateCatalog` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `UpdateClassifier` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `UpdateColumnStatisticsForPartition` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `UpdateColumnStatisticsForTable` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `UpdateColumnStatisticsTaskSettings` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `UpdateConnection` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `UpdateCrawler` | `NOT_PLANNED` | Glue Job/JobRun/Crawler family excluded |
| GLUE | `UpdateCrawlerSchedule` | `NOT_PLANNED` | Glue Job/JobRun/Crawler family excluded |
| GLUE | `UpdateDataQualityRuleset` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `UpdateDatabase` | `COMPATIBLE` | Implemented with boto3 contracts and public Proxy E2E |
| GLUE | `UpdateDevEndpoint` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `UpdateGlossary` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `UpdateGlossaryTerm` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `UpdateGlueIdentityCenterConfiguration` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `UpdateIntegrationResourceProperty` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `UpdateIntegrationTableProperties` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `UpdateJob` | `NOT_PLANNED` | Glue Job/JobRun/Crawler family excluded |
| GLUE | `UpdateJobFromSourceControl` | `NOT_PLANNED` | Glue Job/JobRun/Crawler family excluded |
| GLUE | `UpdateMLTransform` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `UpdatePartition` | `COMPATIBLE` | Implemented with boto3 contracts and public Proxy E2E |
| GLUE | `UpdateRegistry` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `UpdateSchema` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `UpdateSourceControlFromJob` | `NOT_PLANNED` | Glue Job/JobRun/Crawler family excluded |
| GLUE | `UpdateTable` | `COMPATIBLE` | Implemented with boto3 contracts and public Proxy E2E |
| GLUE | `UpdateTableOptimizer` | `COMPATIBLE` | Implemented with boto3 contracts and public Proxy E2E |
| GLUE | `UpdateTrigger` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `UpdateUsageProfile` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `UpdateUserDefinedFunction` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
| GLUE | `UpdateWorkflow` | `PROTOCOL_ONLY` | Pinned wire model tracked; semantics pending |
