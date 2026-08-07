# Support scope

[한국어](support-scope.ko.md) | English

This document distinguishes implemented behavior from long-term targets. “Target” never means that the current build is already compatible.

| Area | Current status | Target |
| --- | --- | --- |
| Extensible proxy registry | Implemented, unit tested | Any AWS JSON/SigV4 emulator can register without proxy code changes |
| AWS JSON 1.1 codec/model validation | Implemented, unit tested | EMR and Glue modeled request/response/error coverage |
| LocalStack fallback | Implemented, unit tested | Transparent non-EMR/Glue forwarding |
| EMR control plane | In development | Broad public EMR API compatibility |
| EMR bootstrap/Spark | In development | Real Spark 3.5.x local execution with LocalStack S3 |
| Glue Data Catalog | In development | Database/table/version/partition/UDF and documented errors |
| Spark + Hive + Glue Catalog | In development | Hive-compatible metadata interoperability |
| Spark + Iceberg + Glue Catalog | In development | Iceberg 1.7.1 read/write on LocalStack S3 |
| Web console | Planned | EMR and Glue Catalog resource/status/log views |

## Explicit exclusions

- AWS Glue Job and JobRun APIs
- AWS Glue Crawlers
- undocumented AWS bug reproduction
- production IAM authorization semantics in default local mode
- physical EC2/YARN/HDFS distribution fidelity

## Version baseline

- Python API services: Python 3.11, tested on 3.11 and 3.12
- Protocol model: botocore 1.43.66; tracked by `contracts/service-model-manifest.json`
- Spark: 3.5.x; Glue interoperability profile uses Spark 3.5.4
- Java: 17
- Iceberg: 1.7.1 for the Glue 5.0 profile

The Glue runtime versions follow [AWS Glue versions](https://docs.aws.amazon.com/glue/latest/dg/release-notes.html) and the [official Glue 5 local image](https://docs.aws.amazon.com/glue/latest/dg/develop-local-docker-image.html). EMR semantics follow the [EMR API Reference](https://docs.aws.amazon.com/emr/latest/APIReference/Welcome.html).

