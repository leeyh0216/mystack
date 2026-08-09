<!-- doc-id: protocols/emr-startup-clusters -->
<!-- lang: ko -->

[한국어](emr-startup-clusters.ko.md) | [English](emr-startup-clusters.md)

# EMR 시작 클러스터 파일

<!-- toc:start -->
## 목차

- [Versioned 형식](#versioned-형식)
- [검증과 시작 동작](#검증과-시작-동작)
- [게시 image의 Compose 사용법](#게시-image의-compose-사용법)
- [진단과 유지보수](#진단과-유지보수)
- [공식 참고 자료](#공식-참고-자료)
<!-- toc:end -->

Mystack은 health endpoint가 준비되기 전에 검토된 process-local EMR cluster 목록을 생성할 수
있습니다. 이 기능은 emulator 배포 입력이며 새로운 AWS operation이 아닙니다. 각 `clusters`
entry는 공식 [`RunJobFlow` 요청 member](https://docs.aws.amazon.com/emr/latest/APIReference/API_RunJobFlow.html)를
사용하며 boto3 요청과 같은 command 및 lifecycle 경로로 들어갑니다.

<!-- section: format -->
## Versioned 형식

Root는 의도적으로 단순하며 unknown key를 거부합니다.

```yaml
schema_version: 1
clusters:
  - Name: local-analytics
    ReleaseLabel: emr-7.8.0
    Instances:
      InstanceCount: 1
      KeepJobFlowAliveWhenNoSteps: true
    Applications:
      - Name: Spark
    Tags:
      - Key: provisioned-by
        Value: startup-file
```

지원하는 entry member는 `Name`, `ReleaseLabel`, `Instances`, `Applications`,
`BootstrapActions`, `Steps`, `LogUri`, `ServiceRole`, `VisibleToAllUsers`,
`StepConcurrencyLevel`, `Tags`입니다. 상위 botocore model에 member가 있어도 Mystack이
emulation하지 않으면 거부할 수 있습니다. 유효해 보이는 file에서 사용자의 의도를 조용히
누락하지 않기 위함입니다. 초기 bootstrap action과 Step에도 일반 [지원 범위](../support-scope.ko.md)가
적용됩니다.

<!-- section: validation -->
## 검증과 시작 동작

첫 cluster를 만들기 전에 YAML 전체를 parse하고 모든 entry를 고정 botocore `RunJobFlow` model,
구현 member allowlist, 설정한 release profile, 중복 이름, Step limit으로 검증합니다. 하나라도
실패하면 EMR HTTP server가 healthy 상태가 되지 않습니다. 일부만 검증된 plan은 실행하지 않습니다.

검증 후 inbound file adapter가 entry를 기술 독립적인 `CreateCluster` command로 mapping하고 file
순서대로 기존 application port를 호출합니다. Repository에 직접 쓰지 않습니다. Bootstrap action과
초기 Step은 boto3 요청과 같은 queue driver에서 비동기로 이어집니다. 따라서 `ListClusters`,
`DescribeCluster`, management resource endpoint와 Console이 같은 aggregate를 봅니다.

현재 EMR repository는 process-local입니다. EMR container를 다시 시작하면 새 cluster ID로 설정
목록을 다시 만들며 이전 ID를 보존하거나 이름을 reconcile하지 않습니다. 결정적인 file
fingerprint와 설정 개수는 health 및 management 응답에서 확인할 수 있습니다.

<!-- section: docker -->
## 게시 image의 Compose 사용법

Image와 같은 release tag에서 overlay와 sample을 받습니다. Docker의 [bind mount
계약](https://docs.docker.com/engine/storage/bind-mounts/)에 따라 명시적인 read-only mount를
사용합니다.

```bash
gh api -H "Accept: application/vnd.github.raw+json" \
  "repos/leeyh0216/mystack/contents/compose.emr-startup-clusters.yaml?ref=$MYSTACK_IMAGE_TAG" \
  > compose.emr-startup-clusters.yaml
gh api -H "Accept: application/vnd.github.raw+json" \
  "repos/leeyh0216/mystack/contents/config/emr-clusters.example.yaml?ref=$MYSTACK_IMAGE_TAG" \
  > emr-clusters.yaml

export MYSTACK_EMR_STARTUP_CLUSTERS_FILE="$PWD/emr-clusters.yaml"
docker compose -f compose.ghcr.yaml -f compose.emr-startup-clusters.yaml \
  up --detach --wait --wait-timeout 300
```

Mounted main configuration의 `emr.startup_clusters_file`을 지정해도 됩니다. Relative path는 main
configuration file 옆을 기준으로 해석합니다. Nested environment override는
`MYSTACK__EMR__STARTUP_CLUSTERS_FILE`이며 `null`이면 비활성화됩니다. External file 수정 후 EMR을
재시작하면 새 plan을 원자적으로 적용합니다.

<!-- section: diagnose -->
## 진단과 유지보수

`emr.startup_clusters.load.*`, `emr.startup_clusters.provision.*`,
`emr.startup_cluster.create.*` 구조화 event를 확인하세요. Bootstrap argument나 environment
secret은 기록하지 않고 source, fingerprint, definition index, 개수, cluster identity, 수정 위치를
남깁니다. 새 boto3/botocore 입력이 검증되지 않으면 고정 model manifest와 generic validator를 먼저
확인한 뒤 `emr/adapters/inbound/startup.py`와 `aws_shapes.py`의 지원 member 및 mapping을
수정하세요.

<!-- section: sources -->
## 공식 참고 자료

- [Amazon EMR RunJobFlow](https://docs.aws.amazon.com/emr/latest/APIReference/API_RunJobFlow.html)
- [Amazon EMR bootstrap action](https://docs.aws.amazon.com/emr/latest/ManagementGuide/emr-plan-bootstrap.html)
- [Docker bind mount](https://docs.docker.com/engine/storage/bind-mounts/)
