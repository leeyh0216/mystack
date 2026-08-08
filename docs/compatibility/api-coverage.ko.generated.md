# 생성된 API 호환성 Matrix

이 파일은 `contracts/api-coverage.json`에서 생성됩니다. 직접 수정하지 마세요. 공식 inventory는 [botocore service model](https://github.com/boto/botocore/tree/develop/botocore/data)입니다.

botocore: `1.43.66`

## 요약

| Service | COMPATIBLE | PARTIAL | PROTOCOL_ONLY | NOT_PLANNED | Total |
| --- | ---: | ---: | ---: | ---: | ---: |
| EMR | 13 | 0 | 52 | 0 | 65 |
| GLUE | 22 | 0 | 249 | 28 | 299 |

| 서비스 | Operation | 상태 | 설명 |
| --- | --- | --- | --- |
| EMR | `AddInstanceFleet` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| EMR | `AddInstanceGroups` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| EMR | `AddJobFlowSteps` | `COMPATIBLE` | boto3 계약 및 public Proxy E2E 구현 |
| EMR | `AddTags` | `COMPATIBLE` | boto3 계약 및 public Proxy E2E 구현 |
| EMR | `CancelSteps` | `COMPATIBLE` | boto3 계약 및 public Proxy E2E 구현 |
| EMR | `CreatePersistentAppUI` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| EMR | `CreateSecurityConfiguration` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| EMR | `CreateStudio` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| EMR | `CreateStudioSessionMapping` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| EMR | `DeleteSecurityConfiguration` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| EMR | `DeleteStudio` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| EMR | `DeleteStudioSessionMapping` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| EMR | `DescribeCluster` | `COMPATIBLE` | boto3 계약 및 public Proxy E2E 구현 |
| EMR | `DescribeJobFlows` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| EMR | `DescribeNotebookExecution` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| EMR | `DescribePersistentAppUI` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| EMR | `DescribeReleaseLabel` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| EMR | `DescribeSecurityConfiguration` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| EMR | `DescribeStep` | `COMPATIBLE` | boto3 계약 및 public Proxy E2E 구현 |
| EMR | `DescribeStudio` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| EMR | `GetAutoTerminationPolicy` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| EMR | `GetBlockPublicAccessConfiguration` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| EMR | `GetClusterSessionCredentials` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| EMR | `GetManagedScalingPolicy` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| EMR | `GetOnClusterAppUIPresignedURL` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| EMR | `GetPersistentAppUIPresignedURL` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| EMR | `GetSession` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| EMR | `GetSessionEndpoint` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| EMR | `GetStudioSessionMapping` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| EMR | `ListBootstrapActions` | `COMPATIBLE` | boto3 계약 및 public Proxy E2E 구현 |
| EMR | `ListClusters` | `COMPATIBLE` | boto3 계약 및 public Proxy E2E 구현 |
| EMR | `ListInstanceFleets` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| EMR | `ListInstanceGroups` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| EMR | `ListInstances` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| EMR | `ListNotebookExecutions` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| EMR | `ListReleaseLabels` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| EMR | `ListSecurityConfigurations` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| EMR | `ListSessions` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| EMR | `ListSteps` | `COMPATIBLE` | boto3 계약 및 public Proxy E2E 구현 |
| EMR | `ListStudioSessionMappings` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| EMR | `ListStudios` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| EMR | `ListSupportedInstanceTypes` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| EMR | `ModifyCluster` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| EMR | `ModifyInstanceFleet` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| EMR | `ModifyInstanceGroups` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| EMR | `PutAutoScalingPolicy` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| EMR | `PutAutoTerminationPolicy` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| EMR | `PutBlockPublicAccessConfiguration` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| EMR | `PutManagedScalingPolicy` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| EMR | `RemoveAutoScalingPolicy` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| EMR | `RemoveAutoTerminationPolicy` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| EMR | `RemoveManagedScalingPolicy` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| EMR | `RemoveTags` | `COMPATIBLE` | boto3 계약 및 public Proxy E2E 구현 |
| EMR | `RunJobFlow` | `COMPATIBLE` | boto3 계약 및 public Proxy E2E 구현 |
| EMR | `SetKeepJobFlowAliveWhenNoSteps` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| EMR | `SetTerminationProtection` | `COMPATIBLE` | boto3 계약 및 public Proxy E2E 구현 |
| EMR | `SetUnhealthyNodeReplacement` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| EMR | `SetVisibleToAllUsers` | `COMPATIBLE` | boto3 계약 및 public Proxy E2E 구현 |
| EMR | `StartNotebookExecution` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| EMR | `StartSession` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| EMR | `StopNotebookExecution` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| EMR | `TerminateJobFlows` | `COMPATIBLE` | boto3 계약 및 public Proxy E2E 구현 |
| EMR | `TerminateSession` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| EMR | `UpdateStudio` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| EMR | `UpdateStudioSessionMapping` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `AssociateGlossaryTerms` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `BatchCreatePartition` | `COMPATIBLE` | boto3 계약 및 public Proxy E2E 구현 |
| GLUE | `BatchDeleteConnection` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `BatchDeletePartition` | `COMPATIBLE` | boto3 계약 및 public Proxy E2E 구현 |
| GLUE | `BatchDeleteTable` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `BatchDeleteTableVersion` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `BatchGetBlueprints` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `BatchGetCrawlers` | `NOT_PLANNED` | Glue Job/JobRun/Crawler 범위 제외 |
| GLUE | `BatchGetCustomEntityTypes` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `BatchGetDataQualityResult` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `BatchGetDataQualityRulesetEvaluationRun` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `BatchGetDevEndpoints` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `BatchGetIterableForms` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `BatchGetJobs` | `NOT_PLANNED` | Glue Job/JobRun/Crawler 범위 제외 |
| GLUE | `BatchGetPartition` | `COMPATIBLE` | boto3 계약 및 public Proxy E2E 구현 |
| GLUE | `BatchGetTableOptimizer` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `BatchGetTriggers` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `BatchGetWorkflows` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `BatchPutDataQualityStatisticAnnotation` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `BatchStopJobRun` | `NOT_PLANNED` | Glue Job/JobRun/Crawler 범위 제외 |
| GLUE | `BatchUpdatePartition` | `COMPATIBLE` | boto3 계약 및 public Proxy E2E 구현 |
| GLUE | `CancelDataQualityRuleRecommendationRun` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `CancelDataQualityRulesetEvaluationRun` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `CancelMLTaskRun` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `CancelStatement` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `CheckSchemaVersionValidity` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `CreateBlueprint` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `CreateCatalog` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `CreateClassifier` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `CreateColumnStatisticsTaskSettings` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `CreateConnection` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `CreateCrawler` | `NOT_PLANNED` | Glue Job/JobRun/Crawler 범위 제외 |
| GLUE | `CreateCustomEntityType` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `CreateDataQualityRuleset` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `CreateDatabase` | `COMPATIBLE` | boto3 계약 및 public Proxy E2E 구현 |
| GLUE | `CreateDevEndpoint` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `CreateGlossary` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `CreateGlossaryTerm` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `CreateGlueIdentityCenterConfiguration` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `CreateIntegration` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `CreateIntegrationResourceProperty` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `CreateIntegrationTableProperties` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `CreateJob` | `NOT_PLANNED` | Glue Job/JobRun/Crawler 범위 제외 |
| GLUE | `CreateMLTransform` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `CreatePartition` | `COMPATIBLE` | boto3 계약 및 public Proxy E2E 구현 |
| GLUE | `CreatePartitionIndex` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `CreateRegistry` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `CreateSchema` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `CreateScript` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `CreateSecurityConfiguration` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `CreateSession` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `CreateTable` | `COMPATIBLE` | boto3 계약 및 public Proxy E2E 구현 |
| GLUE | `CreateTableOptimizer` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `CreateTrigger` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `CreateUsageProfile` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `CreateUserDefinedFunction` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `CreateWorkflow` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `DeleteAsset` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `DeleteAssetType` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `DeleteAttachment` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `DeleteBlueprint` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `DeleteCatalog` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `DeleteClassifier` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `DeleteColumnStatisticsForPartition` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `DeleteColumnStatisticsForTable` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `DeleteColumnStatisticsTaskSettings` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `DeleteConnection` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `DeleteConnectionType` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `DeleteCrawler` | `NOT_PLANNED` | Glue Job/JobRun/Crawler 범위 제외 |
| GLUE | `DeleteCustomEntityType` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `DeleteDataQualityRuleset` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `DeleteDatabase` | `COMPATIBLE` | boto3 계약 및 public Proxy E2E 구현 |
| GLUE | `DeleteDevEndpoint` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `DeleteFormType` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `DeleteGlossary` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `DeleteGlossaryTerm` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `DeleteGlueIdentityCenterConfiguration` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `DeleteIntegration` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `DeleteIntegrationResourceProperty` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `DeleteIntegrationTableProperties` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `DeleteJob` | `NOT_PLANNED` | Glue Job/JobRun/Crawler 범위 제외 |
| GLUE | `DeleteMLTransform` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `DeletePartition` | `COMPATIBLE` | boto3 계약 및 public Proxy E2E 구현 |
| GLUE | `DeletePartitionIndex` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `DeleteRegistry` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `DeleteResourcePolicy` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `DeleteSchema` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `DeleteSchemaVersions` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `DeleteSecurityConfiguration` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `DeleteSession` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `DeleteTable` | `COMPATIBLE` | boto3 계약 및 public Proxy E2E 구현 |
| GLUE | `DeleteTableOptimizer` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `DeleteTableVersion` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `DeleteTrigger` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `DeleteUsageProfile` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `DeleteUserDefinedFunction` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `DeleteWorkflow` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `DescribeConnectionType` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `DescribeEntity` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `DescribeInboundIntegrations` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `DescribeIntegrations` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `DisassociateGlossaryTerms` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `GetAsset` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `GetAssetType` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `GetBlueprint` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `GetBlueprintRun` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `GetBlueprintRuns` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `GetCatalog` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `GetCatalogImportStatus` | `COMPATIBLE` | boto3 계약 및 public Proxy E2E 구현 |
| GLUE | `GetCatalogs` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `GetClassifier` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `GetClassifiers` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `GetColumnStatisticsForPartition` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `GetColumnStatisticsForTable` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `GetColumnStatisticsTaskRun` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `GetColumnStatisticsTaskRuns` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `GetColumnStatisticsTaskSettings` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `GetConnection` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `GetConnections` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `GetCrawler` | `NOT_PLANNED` | Glue Job/JobRun/Crawler 범위 제외 |
| GLUE | `GetCrawlerMetrics` | `NOT_PLANNED` | Glue Job/JobRun/Crawler 범위 제외 |
| GLUE | `GetCrawlers` | `NOT_PLANNED` | Glue Job/JobRun/Crawler 범위 제외 |
| GLUE | `GetCustomEntityType` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `GetDashboardUrl` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `GetDataCatalogEncryptionSettings` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `GetDataCatalogExportConfiguration` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `GetDataQualityModel` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `GetDataQualityModelResult` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `GetDataQualityResult` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `GetDataQualityRuleRecommendationRun` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `GetDataQualityRuleset` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `GetDataQualityRulesetEvaluationRun` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `GetDatabase` | `COMPATIBLE` | boto3 계약 및 public Proxy E2E 구현 |
| GLUE | `GetDatabases` | `COMPATIBLE` | boto3 계약 및 public Proxy E2E 구현 |
| GLUE | `GetDataflowGraph` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `GetDevEndpoint` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `GetDevEndpoints` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `GetEntityRecords` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `GetFormType` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `GetGlossary` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `GetGlossaryTerm` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `GetGlueIdentityCenterConfiguration` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `GetIntegrationResourceProperty` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `GetIntegrationTableProperties` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `GetJob` | `NOT_PLANNED` | Glue Job/JobRun/Crawler 범위 제외 |
| GLUE | `GetJobBookmark` | `NOT_PLANNED` | Glue Job/JobRun/Crawler 범위 제외 |
| GLUE | `GetJobRun` | `NOT_PLANNED` | Glue Job/JobRun/Crawler 범위 제외 |
| GLUE | `GetJobRuns` | `NOT_PLANNED` | Glue Job/JobRun/Crawler 범위 제외 |
| GLUE | `GetJobs` | `NOT_PLANNED` | Glue Job/JobRun/Crawler 범위 제외 |
| GLUE | `GetMLTaskRun` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `GetMLTaskRuns` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `GetMLTransform` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `GetMLTransforms` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `GetMapping` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `GetMaterializedViewRefreshTaskRun` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `GetPartition` | `COMPATIBLE` | boto3 계약 및 public Proxy E2E 구현 |
| GLUE | `GetPartitionIndexes` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `GetPartitions` | `COMPATIBLE` | boto3 계약 및 public Proxy E2E 구현 |
| GLUE | `GetPlan` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `GetRegistry` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `GetResourcePolicies` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `GetResourcePolicy` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `GetSchema` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `GetSchemaByDefinition` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `GetSchemaVersion` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `GetSchemaVersionsDiff` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `GetSecurityConfiguration` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `GetSecurityConfigurations` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `GetSession` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `GetSessionEndpoint` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `GetStatement` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `GetTable` | `COMPATIBLE` | boto3 계약 및 public Proxy E2E 구현 |
| GLUE | `GetTableOptimizer` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `GetTableVersion` | `COMPATIBLE` | boto3 계약 및 public Proxy E2E 구현 |
| GLUE | `GetTableVersions` | `COMPATIBLE` | boto3 계약 및 public Proxy E2E 구현 |
| GLUE | `GetTables` | `COMPATIBLE` | boto3 계약 및 public Proxy E2E 구현 |
| GLUE | `GetTags` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `GetTrigger` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `GetTriggers` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `GetUnfilteredPartitionMetadata` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `GetUnfilteredPartitionsMetadata` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `GetUnfilteredTableMetadata` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `GetUsageProfile` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `GetUserDefinedFunction` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `GetUserDefinedFunctions` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `GetWorkflow` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `GetWorkflowRun` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `GetWorkflowRunProperties` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `GetWorkflowRuns` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `ImportCatalogToGlue` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `ListAssetTypes` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `ListBlueprints` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `ListColumnStatisticsTaskRuns` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `ListConnectionTypes` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `ListCrawlers` | `NOT_PLANNED` | Glue Job/JobRun/Crawler 범위 제외 |
| GLUE | `ListCrawls` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `ListCustomEntityTypes` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `ListDataQualityResults` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `ListDataQualityRuleRecommendationRuns` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `ListDataQualityRulesetEvaluationRuns` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `ListDataQualityRulesets` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `ListDataQualityStatisticAnnotations` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `ListDataQualityStatistics` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `ListDevEndpoints` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `ListEntities` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `ListFormTypes` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `ListGlossaries` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `ListGlossaryTerms` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `ListIntegrationResourceProperties` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `ListIterableForms` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `ListJobs` | `NOT_PLANNED` | Glue Job/JobRun/Crawler 범위 제외 |
| GLUE | `ListMLTransforms` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `ListMaterializedViewRefreshTaskRuns` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `ListRegistries` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `ListSchemaVersions` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `ListSchemas` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `ListSessions` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `ListStatements` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `ListTableOptimizerRuns` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `ListTriggers` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `ListUsageProfiles` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `ListWorkflows` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `ModifyIntegration` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `PutAsset` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `PutAssetType` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `PutAttachment` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `PutDataCatalogEncryptionSettings` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `PutDataCatalogExportConfiguration` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `PutDataQualityProfileAnnotation` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `PutFormType` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `PutResourcePolicy` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `PutSchemaVersionMetadata` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `PutWorkflowRunProperties` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `QuerySchemaVersionMetadata` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `RegisterConnectionType` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `RegisterSchemaVersion` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `RemoveSchemaVersionMetadata` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `ResetJobBookmark` | `NOT_PLANNED` | Glue Job/JobRun/Crawler 범위 제외 |
| GLUE | `ResumeWorkflowRun` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `RunStatement` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `SearchAssets` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `SearchTables` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `StartBlueprintRun` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `StartColumnStatisticsTaskRun` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `StartColumnStatisticsTaskRunSchedule` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `StartCrawler` | `NOT_PLANNED` | Glue Job/JobRun/Crawler 범위 제외 |
| GLUE | `StartCrawlerSchedule` | `NOT_PLANNED` | Glue Job/JobRun/Crawler 범위 제외 |
| GLUE | `StartDataQualityRuleRecommendationRun` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `StartDataQualityRulesetEvaluationRun` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `StartExportLabelsTaskRun` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `StartImportLabelsTaskRun` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `StartJobRun` | `NOT_PLANNED` | Glue Job/JobRun/Crawler 범위 제외 |
| GLUE | `StartMLEvaluationTaskRun` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `StartMLLabelingSetGenerationTaskRun` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `StartMaterializedViewRefreshTaskRun` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `StartTrigger` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `StartWorkflowRun` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `StopColumnStatisticsTaskRun` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `StopColumnStatisticsTaskRunSchedule` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `StopCrawler` | `NOT_PLANNED` | Glue Job/JobRun/Crawler 범위 제외 |
| GLUE | `StopCrawlerSchedule` | `NOT_PLANNED` | Glue Job/JobRun/Crawler 범위 제외 |
| GLUE | `StopMaterializedViewRefreshTaskRun` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `StopSession` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `StopTrigger` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `StopWorkflowRun` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `TagResource` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `TestConnection` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `UntagResource` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `UpdateAsset` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `UpdateBlueprint` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `UpdateCatalog` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `UpdateClassifier` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `UpdateColumnStatisticsForPartition` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `UpdateColumnStatisticsForTable` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `UpdateColumnStatisticsTaskSettings` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `UpdateConnection` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `UpdateCrawler` | `NOT_PLANNED` | Glue Job/JobRun/Crawler 범위 제외 |
| GLUE | `UpdateCrawlerSchedule` | `NOT_PLANNED` | Glue Job/JobRun/Crawler 범위 제외 |
| GLUE | `UpdateDataQualityRuleset` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `UpdateDatabase` | `COMPATIBLE` | boto3 계약 및 public Proxy E2E 구현 |
| GLUE | `UpdateDevEndpoint` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `UpdateGlossary` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `UpdateGlossaryTerm` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `UpdateGlueIdentityCenterConfiguration` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `UpdateIntegrationResourceProperty` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `UpdateIntegrationTableProperties` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `UpdateJob` | `NOT_PLANNED` | Glue Job/JobRun/Crawler 범위 제외 |
| GLUE | `UpdateJobFromSourceControl` | `NOT_PLANNED` | Glue Job/JobRun/Crawler 범위 제외 |
| GLUE | `UpdateMLTransform` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `UpdatePartition` | `COMPATIBLE` | boto3 계약 및 public Proxy E2E 구현 |
| GLUE | `UpdateRegistry` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `UpdateSchema` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `UpdateSourceControlFromJob` | `NOT_PLANNED` | Glue Job/JobRun/Crawler 범위 제외 |
| GLUE | `UpdateTable` | `COMPATIBLE` | boto3 계약 및 public Proxy E2E 구현 |
| GLUE | `UpdateTableOptimizer` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `UpdateTrigger` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `UpdateUsageProfile` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `UpdateUserDefinedFunction` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
| GLUE | `UpdateWorkflow` | `PROTOCOL_ONLY` | 고정 wire model만 추적, 의미 구현 대기 |
