<!-- doc-id: operations-guide -->
<!-- lang: ko -->

[한국어](operations.ko.md) | [English](operations.md)

# 운영

<!-- toc:start -->
## 목차

- [Service UI 열기](#service-ui-열기)
- [Health, log, 진단 확인](#health-log-진단-확인)
- [설정 파일 mount](#설정-파일-mount)
- [Upgrade, rollback, 정리](#upgrade-rollback-정리)
- [공식 참고 자료](#공식-참고-자료)
<!-- toc:end -->

실행 중인 stack을 확인하고, 서비스가 소유하는 UI를 사용하고, 설정 파일을 mount하거나, 로컬
환경을 중지할 때 이 문서를 사용합니다.

<!-- section: ui -->
## Service UI 열기

EMR UI에서 cluster를 만들고 Step을 제출·추적하며 제출한 command vector와 live 또는 게시된 log를
확인합니다.

```text
http://localhost:4566/_mystack/ui/emr/
```

Glue UI에서 database, table, schema, partition, parameter, raw 메타데이터를 탐색합니다.

```text
http://localhost:4566/_mystack/ui/glue/
```

선택한 resource는 URL에 반영됩니다. Browser를 새로 고치거나 history를 사용하거나 선택한 cluster,
Step, table, partition link를 공유할 수 있습니다. UI route와 streaming 계약은
[관리 UI reference](console.ko.md)를 참고하세요.

<!-- section: diagnostics -->
## Health, log, 진단 확인

`compose.ghcr.yaml`이 있는 directory에서 다음 명령을 실행합니다.

```bash
docker compose -f compose.ghcr.yaml ps
docker compose -f compose.ghcr.yaml logs --tail 200 proxy glue emr
curl --fail http://localhost:4566/_mystack/routes
curl --fail http://localhost:4566/_mystack/diagnostics/threads
curl --fail http://localhost:4566/_mystack/diagnostics/tasks
```

Application stdout, stderr, command argument, S3 log 게시 상태는 EMR Step page에서 먼저
확인합니다. Request나 subprocess가 멈춘 경우에는 서비스 log와 진단 엔드포인트를 사용합니다.
Event field와 문제 해결 경계는 [관측성 안내](observability.ko.md)에 있습니다.

<!-- section: configuration -->
## 설정 파일 mount

실행할 image version과 같은 설정 및 Compose overlay를 내려받고 모든 Mystack 서비스에
read-only로 mount합니다.

```bash
curl --fail --location --output mystack.yaml \
  "https://raw.githubusercontent.com/leeyh0216/mystack/$MYSTACK_IMAGE_TAG/config/runtime/mystack.yaml"
curl --fail --location --output compose.mount-config.yaml \
  "https://raw.githubusercontent.com/leeyh0216/mystack/$MYSTACK_IMAGE_TAG/compose.mount-config.yaml"

export MYSTACK_CONFIG_FILE="$PWD/mystack.yaml"
docker compose \
  -f compose.ghcr.yaml \
  -f compose.mount-config.yaml \
  up --detach --wait --wait-timeout 300
```

Mount한 파일을 변경한 뒤에는 영향을 받는 서비스를 재시작합니다. Setting 이름, override 우선순위,
제한 시간 값은 [설정 reference](configuration.ko.md)를 참고하세요.

<!-- section: lifecycle -->
## Upgrade, rollback, 정리

Upgrade 또는 rollback할 때는 `MYSTACK_IMAGE_TAG`를 대상 version으로 정하고 같은 version의
`compose.ghcr.yaml`을 받은 뒤 stack을 pull하고 다시 만듭니다.

```bash
docker compose -f compose.ghcr.yaml pull
docker compose -f compose.ghcr.yaml up --detach --wait --wait-timeout 300
```

이전에 검증한 version으로 같은 명령을 실행하면 rollback합니다. 종료 명령은 data에 미치는 영향이
다릅니다.

```bash
docker compose -f compose.ghcr.yaml stop
docker compose -f compose.ghcr.yaml down
docker compose -f compose.ghcr.yaml down --volumes
```

`stop`은 container와 data를 보존합니다. `down`은 container를 제거하고 named volume은
유지합니다. `down --volumes`는 EMR, Glue, LocalStack state를 영구히 제거합니다.

<!-- section: sources -->
## 공식 참고 자료

- [Docker Compose command reference](https://docs.docker.com/reference/cli/docker/compose/)
- [Docker Compose file 병합](https://docs.docker.com/compose/how-tos/multiple-compose-files/merge/)
- [Amazon EMR log file](https://docs.aws.amazon.com/emr/latest/ManagementGuide/emr-manage-view-web-log-files.html)
