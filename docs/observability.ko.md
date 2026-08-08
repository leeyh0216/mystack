<!-- doc-id: observability -->
<!-- lang: ko -->

[한국어](observability.ko.md) | [English](observability.md)

# 관찰성과 진단

Mystack은 Controller, component 경계, 상태 전이, 모든 외부 side effect에서 구조화 JSON을 기록합니다. 기준은 [AWS Well-Architected observability 지침](https://docs.aws.amazon.com/wellarchitected/latest/operational-excellence-pillar/observability.html)입니다.

<!-- section: event-phases -->
## 필수 event 단계

- 작업 전 `*.received` 또는 `*.started`
- 성공 후 duration과 결과 metadata를 가진 `*.completed`
- 기술 실패 시 exception과 실행 가능한 `fix_hint`를 가진 `*.failed`
- Python traceback 없이 modeled AWS 동작을 나타내는 `*.service_error`
- 시작 시 검토한 operation family를 조립하는 `protocol.operation_registry.*`
- before/after/reason을 가진 Domain 상태 `*.transitioned`

Repository, S3, process, container, outbound HTTP adapter는 해당 단계를 모두 기록해야 합니다.

Console read는 기술 실패를 포함해 전·후에 `proxy.management.*`, `emr.management.*`,
`glue.management.*`를 기록합니다. EMR Console command는 일반 AWS protocol request이므로
`proxy.forward.*`, `controller.request.*`, `application.dispatch.*`, Domain transition event가
operation과 request ID를 보존합니다. 변경된 boto/botocore request가 더는 올바르게 routing되지
않으면 `proxy.routing.fallback`에서 먼저 확인할 수 있고 modeled AWS rejection은 기술 traceback이
아니라 `*.service_error`로 남습니다.

EMR LogUri 게시는 전체 archive 전후에 `emr.step_logs.publish.*`, 각 S3 object 전후에
`emr.step_log_object.put.*`를 기록합니다. 실패 event는 cluster/Step, 안전한 bucket/key 정보,
부분 게시 object 수와 `fix_hint`를 포함하며 local publication record는 management endpoint에서
확인할 수 있습니다. 자세한 계약은 [log 배치](protocols/emr-log-layout.ko.md)에 있습니다.

미리 구성한 cluster는 전체 file 검증 전후에 `emr.startup_clusters.load.*`, plan 실행 전후에
`emr.startup_clusters.provision.*`, application port 호출마다 `emr.startup_cluster.create.*`를
기록합니다. Source, fingerprint, 안전한 개수, definition index, cluster ID, 수정 위치를 통해 향후
botocore mapping 변경을 진단할 수 있습니다. 자세한 내용은 [시작 클러스터
계약](protocols/emr-startup-clusters.ko.md)에 있습니다.

신뢰된 image 초기화는 `emr.prestart.scan.*`, file별
`emr.prestart.script.before`/`after`/`failed`,
`emr.entrypoint.privilege_drop.before`/`failed`를 남깁니다. Script basename, 안전한 소유권과 mode,
SHA-256 prefix, 실행 시간 또는 exit code, `fix_hint`만 기록하며 값과 script 내용은 보호합니다.
[EMR pre-start 계약](protocols/emr-prestart.ko.md)을 참고하세요.

<!-- section: fields -->
## 공통 field

상황에 따라 `service`, `component`, `request_id`, `operation`, `api_version`, `model_fingerprint`, `resource_id`, `state_before`, `state_after`, `duration_ms`, `fix_hint`를 사용합니다.

Authorization, access/secret key, management token, 전체 request payload, frame locals는 기록하지 않습니다. Payload 진단은 byte length와 SHA-256 prefix, 설정 로그는 source·fingerprint·redacted override path만 사용합니다.

<!-- section: diagnostics -->
## Live 진단

- `GET /_mystack/diagnostics/threads`: Python thread와 source stack line
- `GET /_mystack/diagnostics/tasks`: asyncio task와 source stack line

YAML `management.diagnostics.enabled`, `stack_limit`, 선택적 `token`을 따릅니다. Token이 있으면 `Authorization: Bearer ...`가 필요하며 접근 시도를 audit합니다. Python은 [`sys._current_frames`](https://docs.python.org/3/library/sys.html#sys._current_frames)의 non-deadlocking snapshot 동작을 문서화합니다.

`make threads`, `make tasks`를 사용합니다. Stack source는 locals가 없어도 운영상 민감하므로 공유 배포에서는 management token과 network 제한이 필요합니다.

<!-- section: drift -->
## Upstream drift 진단

모델 로드와 검증 event는 botocore 버전, 서비스 API 버전, 모델 지문, 작업, 입력 구조를
포함합니다. 지문이 바뀌면 protocol facade를 먼저 확인합니다. 작업의 데이터 구조가
바뀌면 해당 서비스 입력 mapper와 계약 시험을 먼저 수정합니다.

`proxy.routing.fallback`은 credential이나 전체 User-Agent 없이 target prefix, SigV4 signing
name, host prefix, content type, parse한 SDK version을 기록합니다. `fix_hint`는 YAML route
metadata만 고칠 상황과 `routing.py`의 evidence parser를 고칠 상황을 구분합니다.

`proxy.forward.completed`는 raw response byte 길이, upstream content encoding, 주입한 client가
이미 body를 decode했는지 나타내는 `response_body_decoded`(일반적으로 `false`)를 기록합니다.
SDK가 S3 flexible checksum 불일치를 보고하면 service emulator나 object payload를 바꾸기 전에
이 event와 `mystack.proxy.forwarder`를 확인합니다.
