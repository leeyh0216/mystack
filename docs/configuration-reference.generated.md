# Generated configuration reference

<!-- toc:start -->
## Contents

- [Complete leaf keys](#complete-leaf-keys)
<!-- toc:end -->

Do not edit: generated from the runtime JSON Schema and `config/mystack.yaml`.
All values load once at process startup; restart the affected service after a change.

## Complete leaf keys

| Path | Type / validation | Default or example | Owner | Effect / reload |
| --- | --- | --- | --- | --- |
| `schema_version` | const=1 | `1` | `schema_version` | Runtime configuration; restart required |
| `logging.level` | enum=['CRITICAL', 'ERROR', 'WARNING', 'INFO', 'DEBUG'] | `"INFO"` | `logging` | Runtime configuration; restart required |
| `logging.format` | const='json' | `"json"` | `logging` | Runtime configuration; restart required |
| `management.console.refresh_interval_seconds` | type='number'; minimum=0.5 | `2` | `management` | Runtime configuration; restart required |
| `management.console.log_stream_poll_interval_seconds` | type='number'; minimum=0.1 | `0.5` | `management` | Runtime configuration; restart required |
| `management.console.log_stream_timeout_seconds` | type='number'; exclusiveMinimum=0 | `300` | `management` | Runtime configuration; restart required |
| `management.console.log_buffer_bytes` | type='integer'; minimum=1024 | `1048576` | `management` | Runtime configuration; restart required |
| `management.diagnostics.enabled` | type='boolean' | `true` | `management` | Runtime configuration; restart required |
| `management.diagnostics.stack_limit` | type='integer'; minimum=1 | `100` | `management` | Runtime configuration; restart required |
| `proxy.listen.host` | type='string'; minLength=1 | `"0.0.0.0"` | `proxy` | Runtime configuration; restart required |
| `proxy.listen.port` | type='integer'; minimum=1; maximum=65535 | `8080` | `proxy` | Runtime configuration; restart required |
| `proxy.fallback_url` | type='string'; format='uri' | `"http://localstack:4566"` | `proxy` | Runtime configuration; restart required |
| `proxy.request_timeout_seconds` | type='number'; exclusiveMinimum=0 | `300` | `proxy` | Runtime configuration; restart required |
| `proxy.routes` | type='array' | `[{"name": "emr", "backend_url": "http://emr:8080", "target_prefixes": ["ElasticMapReduce"], "signing_names": ["elasticmapreduce"], "host_prefixes": ["elasticmapreduce", "emr"]}, {"name": "glue", "backend_url": "http://glue:8080", "target_prefixes": ["AWSGlue"], "signing_names": ["glue"], "host_prefixes": ["glue"]}]` | `proxy` | Runtime configuration; restart required |
| `localstack.endpoint_url` | type='string'; format='uri' | `"http://localstack:4566"` | `localstack` | Runtime configuration; restart required |
| `localstack.region` | type='string'; minLength=1 | `"us-east-1"` | `localstack` | Runtime configuration; restart required |
| `localstack.account_id` | type='string'; pattern='^[0-9]{12}$' | `"000000000000"` | `localstack` | Runtime configuration; restart required |
| `localstack.access_key_id` | type='string'; minLength=1 | `"test"` | `localstack` | Runtime configuration; restart required |
| `localstack.secret_access_key` | type='string'; minLength=1 | `"test"` | `localstack` | Runtime configuration; restart required |
| `localstack.s3_path_style` | type='boolean' | `true` | `localstack` | Runtime configuration; restart required |
| `emr.listen.host` | type='string'; minLength=1 | `"0.0.0.0"` | `emr` | Runtime configuration; restart required |
| `emr.listen.port` | type='integer'; minimum=1; maximum=65535 | `8080` | `emr` | Runtime configuration; restart required |
| `emr.work_root` | type='string'; minLength=1 | `"/var/lib/mystack/emr"` | `emr` | Runtime configuration; restart required |
| `emr.process_timeout_seconds` | type='number'; exclusiveMinimum=0 | `3600` | `emr` | Runtime configuration; restart required |
| `emr.bootstrap_timeout_seconds` | type='number'; exclusiveMinimum=0 | `900` | `emr` | Runtime configuration; restart required |
| `emr.bootstrap_shell` | type='string'; minLength=1 | `"/bin/bash"` | `emr` | Runtime configuration; restart required |
| `emr.terminate_grace_seconds` | type='number'; exclusiveMinimum=0 | `10` | `emr` | Runtime configuration; restart required |
| `emr.shutdown_timeout_seconds` | type='number'; exclusiveMinimum=0 | `30` | `emr` | Runtime configuration; restart required |
| `emr.output_tail_bytes` | type='integer'; minimum=1 | `32768` | `emr` | Runtime configuration; restart required |
| `emr.live_log_chunk_bytes` | type='integer'; minimum=1 | `16384` | `emr` | Runtime configuration; restart required |
| `emr.log_retention_seconds` | type='number'; exclusiveMinimum=0 | `604800` | `emr` | Runtime configuration; restart required |
| `emr.log_publication.max_attempts` | type='integer'; minimum=1 | `3` | `emr` | Runtime configuration; restart required |
| `emr.log_publication.initial_backoff_seconds` | type='number'; minimum=0 | `0.5` | `emr` | Runtime configuration; restart required |
| `emr.log_publication.max_backoff_seconds` | type='number'; minimum=0 | `10` | `emr` | Runtime configuration; restart required |
| `emr.log_publication.attempt_timeout_seconds` | type='number'; exclusiveMinimum=0 | `60` | `emr` | Runtime configuration; restart required |
| `emr.spark_ui.port_min` | type='integer'; minimum=1024; maximum=65535 | `4040` | `emr` | Runtime configuration; restart required |
| `emr.spark_ui.port_max` | type='integer'; minimum=1024; maximum=65535 | `4059` | `emr` | Runtime configuration; restart required |
| `emr.startup_clusters_file` | type=['string', 'null']; minLength=1 | `null` | `emr` | Runtime configuration; restart required |
| `emr.command_runner_jars` | type='array'; minItems=1 | `["command-runner.jar"]` | `emr` | Runtime configuration; restart required |
| `emr.api_page_size` | type='integer'; minimum=1 | `50` | `emr` | Runtime configuration; restart required |
| `emr.max_active_steps` | type='integer'; minimum=1 | `256` | `emr` | Runtime configuration; restart required |
| `emr.default_release_label` | type='string'; minLength=1 | `"emr-7.8.0"` | `emr` | Runtime configuration; restart required |
| `emr.release_profiles.emr-7.8.0.runtime_profile` | type='string'; minLength=1 | `"spark-3.5.4"` | `emr` | Runtime configuration; restart required |
| `emr.release_profiles.emr-7.8.0.aws_spark_version` | type='string'; minLength=1 | `"3.5.4-amzn-0"` | `emr` | Runtime configuration; restart required |
| `emr.release_profiles.emr-7.8.0.source` | type='string'; format='uri' | `"https://docs.aws.amazon.com/emr/latest/ReleaseGuide/emr-release-app-versions-7.x.html"` | `emr` | Runtime configuration; restart required |
| `glue.listen.host` | type='string'; minLength=1 | `"0.0.0.0"` | `glue` | Runtime configuration; restart required |
| `glue.listen.port` | type='integer'; minimum=1; maximum=65535 | `8080` | `glue` | Runtime configuration; restart required |
| `glue.data_root` | type='string'; minLength=1 | `"/var/lib/mystack/glue"` | `glue` | Runtime configuration; restart required |
| `glue.sqlite.database_file` | type='string'; minLength=1 | `"catalog.sqlite3"` | `glue` | Runtime configuration; restart required |
| `glue.sqlite.driver.module` | type='string'; minLength=1 | `"pysqlite3.dbapi2"` | `glue` | Runtime configuration; restart required |
| `glue.sqlite.driver.expected_version` | type='string'; pattern='^[0-9]+(?:\\.[0-9]+){2,3}$' | `"3.53.4"` | `glue` | Runtime configuration; restart required |
| `glue.sqlite.driver.minimum_wal_version` | type='string'; pattern='^[0-9]+(?:\\.[0-9]+){2,3}$' | `"3.51.3"` | `glue` | Runtime configuration; restart required |
| `glue.sqlite.driver.manifest_file` | type='string'; minLength=1 | `"/opt/mystack/sqlite-runtime/runtime-manifest.json"` | `glue` | Runtime configuration; restart required |
| `glue.sqlite.journal_mode` | enum=['wal', 'rollback'] | `"wal"` | `glue` | Runtime configuration; restart required |
| `glue.sqlite.synchronous` | enum=['off', 'normal', 'full', 'extra'] | `"normal"` | `glue` | Runtime configuration; restart required |
| `glue.sqlite.busy_timeout_milliseconds` | type='integer'; minimum=1 | `5000` | `glue` | Runtime configuration; restart required |
| `glue.sqlite.retry_limit` | type='integer'; minimum=0 | `3` | `glue` | Runtime configuration; restart required |
| `glue.sqlite.checkpoint.mode` | enum=['passive', 'full', 'restart', 'truncate'] | `"passive"` | `glue` | Runtime configuration; restart required |
| `glue.sqlite.checkpoint.auto_checkpoint_pages` | type='integer'; minimum=0 | `1000` | `glue` | Runtime configuration; restart required |
| `glue.catalog_id` | type='string'; pattern='^[0-9]{12}$' | `"000000000000"` | `glue` | Runtime configuration; restart required |
| `glue.api_page_size` | type='integer'; minimum=1 | `100` | `glue` | Runtime configuration; restart required |
| `glue.create_default_database` | type='boolean' | `true` | `glue` | Runtime configuration; restart required |
| `glue.partition_expressions.max_length` | type='integer'; minimum=1 | `2048` | `glue` | Runtime configuration; restart required |
| `glue.partition_expressions.max_tokens` | type='integer'; minimum=1 | `512` | `glue` | Runtime configuration; restart required |
| `glue.partition_expressions.supported_key_types` | type='array'; minItems=1 | `["string", "date", "timestamp", "int", "bigint", "long", "tinyint", "smallint", "decimal"]` | `glue` | Runtime configuration; restart required |
| `glue.fault_injection.enabled` | type='boolean' | `false` | `glue` | Runtime configuration; restart required |
| `glue.fault_injection.rules` | type='array' | `[]` | `glue` | Runtime configuration; restart required |
| `glue.table_optimizers.enabled` | type='boolean' | `true` | `glue` | Runtime configuration; restart required |
| `glue.table_optimizers.work_root` | type='string'; minLength=1 | `"table-optimizer-runs"` | `glue` | Runtime configuration; restart required |
| `glue.table_optimizers.catalog_endpoint_url` | type='string'; format='uri' | `"http://127.0.0.1:8080"` | `glue` | Runtime configuration; restart required |
| `glue.table_optimizers.catalog_name` | type='string'; minLength=1 | `"mystack"` | `glue` | Runtime configuration; restart required |
| `glue.table_optimizers.scheduler.poll_interval_seconds` | type='number'; exclusiveMinimum=0 | `2` | `glue` | Runtime configuration; restart required |
| `glue.table_optimizers.scheduler.initial_delay_seconds` | type='number'; minimum=0 | `2` | `glue` | Runtime configuration; restart required |
| `glue.table_optimizers.scheduler.max_concurrent_runs` | type='integer'; minimum=1 | `1` | `glue` | Runtime configuration; restart required |
| `glue.table_optimizers.scheduler.compaction_interval_seconds` | type='number'; exclusiveMinimum=0 | `86400` | `glue` | Runtime configuration; restart required |
| `glue.table_optimizers.scheduler.history_limit` | type='integer'; minimum=1 | `100` | `glue` | Runtime configuration; restart required |
| `glue.table_optimizers.scheduler.compaction_failure_limit` | type='integer'; minimum=1 | `4` | `glue` | Runtime configuration; restart required |
| `glue.table_optimizers.worker.spark_submit` | type='string'; minLength=1 | `"/opt/mystack/bin/spark-submit"` | `glue` | Runtime configuration; restart required |
| `glue.table_optimizers.worker.submit_args` | type='array' | `["--master", "local[*]"]` | `glue` | Runtime configuration; restart required |
| `glue.table_optimizers.worker.timeout_seconds` | type='number'; exclusiveMinimum=0 | `1800` | `glue` | Runtime configuration; restart required |
| `glue.table_optimizers.worker.terminate_grace_seconds` | type='number'; exclusiveMinimum=0 | `10` | `glue` | Runtime configuration; restart required |
| `glue.runtime_profile` | type='string'; minLength=1 | `"glue-5.0"` | `glue` | Runtime configuration; restart required |
| `runtime_profiles.spark-3.5.4` | schema-defined | `{"spark_version": "3.5.4", "python_version": "3.11", "java_version": "17", "master": "local[*]", "spark_submit": "/opt/spark/bin/spark-submit", "submit_aliases": ["spark-submit"], "spark_packages": ["org.apache.hadoop:hadoop-aws:3.3.4"], "spark_conf": {"spark.ui.enabled": "false", "spark.driver.bindAddress": "127.0.0.1", "spark.driver.host": "127.0.0.1"}, "option_value_names": ["--archives", "--class", "--conf", "--deploy-mode", "--driver-class-path", "--driver-java-options", "--driver-library-path", "--driver-memory", "--executor-cores", "--executor-memory", "--files", "--jars", "--keytab", "--kill", "--master", "--name", "--packages", "--packages-exclude", "--principal", "--properties-file", "--proxy-user", "--py-files", "--queue", "--repositories", "--status", "--total-executor-cores"]}` | `runtime_profiles` | Runtime configuration; restart required |
| `runtime_profiles.glue-5.0` | schema-defined | `{"base_image": "public.ecr.aws/glue/aws-glue-libs:5", "spark_version": "3.5.4", "python_version": "3.11", "java_version": "17", "iceberg_version": "1.7.1"}` | `runtime_profiles` | Runtime configuration; restart required |
| `tests.unit_timeout_seconds` | type='number'; exclusiveMinimum=0 | `60` | `tests` | Runtime configuration; restart required |
| `tests.contract_timeout_seconds` | type='number'; exclusiveMinimum=0 | `120` | `tests` | Runtime configuration; restart required |
| `tests.package_smoke_timeout_seconds` | type='number'; exclusiveMinimum=0 | `120` | `tests` | Runtime configuration; restart required |
| `tests.compatibility_collection_timeout_seconds` | type='number'; exclusiveMinimum=0 | `30` | `tests` | Runtime configuration; restart required |
| `tests.e2e_timeout_seconds` | type='number'; exclusiveMinimum=0 | `1200` | `tests` | Runtime configuration; restart required |
| `tests.compose_wait_timeout_seconds` | type='number'; exclusiveMinimum=0 | `300` | `tests` | Runtime configuration; restart required |
| `tests.e2e.endpoint_url` | type='string'; format='uri' | `"http://127.0.0.1:4566"` | `tests` | Runtime configuration; restart required |
| `tests.e2e.poll_interval_seconds` | type='number'; exclusiveMinimum=0 | `0.5` | `tests` | Runtime configuration; restart required |
| `tests.e2e.sdk_connect_timeout_seconds` | type='number'; exclusiveMinimum=0 | `5` | `tests` | Runtime configuration; restart required |
| `tests.e2e.sdk_read_timeout_seconds` | type='number'; exclusiveMinimum=0 | `30` | `tests` | Runtime configuration; restart required |
| `tests.e2e.sdk_max_attempts` | type='integer'; minimum=0 | `3` | `tests` | Runtime configuration; restart required |
| `tests.e2e.browser_action_timeout_seconds` | type='number'; exclusiveMinimum=0 | `30` | `tests` | Runtime configuration; restart required |
| `tests.e2e.browser_required_environment_variable` | type='string'; minLength=1 | `"MYSTACK_BROWSER_E2E_REQUIRED"` | `tests` | Runtime configuration; restart required |
| `tests.e2e.compose_file` | type='string'; minLength=1 | `"compose.yaml"` | `tests` | Runtime configuration; restart required |
| `tests.e2e.emr_service` | type='string'; minLength=1 | `"emr"` | `tests` | Runtime configuration; restart required |
| `tests.e2e.emr_jar_fixture_container_path` | type='string'; minLength=1 | `"/opt/mystack/spark-s3-job.jar"` | `tests` | Runtime configuration; restart required |
| `tests.e2e.emr_release_label` | type='string'; minLength=1 | `"emr-7.8.0"` | `tests` | Runtime configuration; restart required |
| `tests.e2e.emr_expected_spark_version_prefix` | type='string'; minLength=1 | `"3.5.4"` | `tests` | Runtime configuration; restart required |
| `tests.e2e.glue_service` | type='string'; minLength=1 | `"glue"` | `tests` | Runtime configuration; restart required |
| `tests.e2e.glue_spark_submit` | type='string'; minLength=1 | `"spark-submit"` | `tests` | Runtime configuration; restart required |
| `tests.e2e.glue_catalog_script` | type='string'; minLength=1 | `"/opt/mystack/e2e/glue_catalog_job.py"` | `tests` | Runtime configuration; restart required |
| `tests.e2e.glue_iceberg_contention_script` | type='string'; minLength=1 | `"/opt/mystack/e2e/iceberg_contention_job.py"` | `tests` | Runtime configuration; restart required |
| `tests.e2e.glue_expected_spark_version_prefix` | type='string'; minLength=1 | `"3.5.4"` | `tests` | Runtime configuration; restart required |
| `tests.e2e.glue_catalog_endpoint_url` | type='string'; format='uri' | `"http://proxy:8080"` | `tests` | Runtime configuration; restart required |
| `tests.e2e.object_store_endpoint_url` | type='string'; format='uri' | `"http://localstack:4566"` | `tests` | Runtime configuration; restart required |
| `tests.e2e.sts_endpoint_url` | type='string'; format='uri' | `"http://localstack:4566"` | `tests` | Runtime configuration; restart required |
| `tests.e2e.artifacts_dir` | type='string'; minLength=1 | `"test-artifacts"` | `tests` | Runtime configuration; restart required |
