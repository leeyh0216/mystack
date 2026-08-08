<!-- doc-id: extensions -->
<!-- lang: ko -->

[한국어](extensions.ko.md) | [English](extensions.md)

# Glue 확장 SPI 안내

Mystack 이미지를 다시 빌드하지 않고 Glue 작업 하나를 교체하거나 감싸거나 오류만
변환할 수 있습니다. Python wheel을 읽기 전용으로 mount하고 YAML에서 provider를
선택합니다. 현재 확장은 Glue 프로세스 안에서 실행됩니다. 신뢰할 수 없는 코드를
격리하는 기능은 아닙니다.

설계 결정은 [권한별 확장 SPI ADR](adr/0003-tiered-extension-spis.ko.md)에 있습니다.

<!-- section: tiers -->
## 세 가지 SPI

| SPI | 사용 시점 | 접근 범위 | 호환성 |
| --- | --- | --- | --- |
| `stable` | 일반적인 오류 보완과 정책 추가 | 동결된 snapshot, application-backed capability | SPI v1 안에서 유지 |
| `application` | domain use case를 직접 합성 | `CatalogApplication`, 공개 domain type | Mystack 부 버전 단위 |
| `unsafe` | 실험, 긴급 복구, 저장 구현 조사 | repository, clock, 설정, application | 정확한 Mystack 버전만 |

가능하면 `stable`부터 사용합니다. `application`은 mutable domain object를 반환할 수
있으므로 `mystack_minor_version`이 현재 설치의 `major.minor`와 같아야 합니다. `unsafe`는
불변 조건을 우회할 수 있으므로 `allow_unsafe: true`와 정확한 `mystack_version`이 모두
필요합니다.

이 경계는 [AWS Hexagonal architecture
지침](https://docs.aws.amazon.com/prescriptive-guidance/latest/hexagonal-architectures/overview.html)에
따라 composition root에서 주입됩니다. Domain과 Application은 사용자 package를 알지
못합니다.

<!-- section: chain -->
## 작업 chain

모든 SPI는 같은 `OperationMiddleware` 계약을 사용합니다.

```python
class OperationMiddleware(Protocol):
    async def invoke(
        self,
        call: OperationCall,
        next_handler: OperationNext,
    ) -> Mapping[str, Any]: ...
```

- `await next_handler(call)` 전에 코드를 실행하면 전처리입니다.
- 호출 결과를 바꾸면 후처리입니다.
- `AwsServiceError`를 잡아서 다시 발생시키면 오류 전용 변환입니다.
- 다음 handler를 호출하지 않고 modeled response를 반환하면 완전 교체입니다.
- 한 middleware는 다음 handler를 한 번만 호출할 수 있습니다.

요청은 공식 botocore 입력 모델을 통과한 뒤 확장에 전달됩니다. 최종 성공 응답은 공식
출력 모델로 다시 검증됩니다. 잘못된 출력은 `InternalServiceException`으로 안전하게
거부합니다. AWS Glue 오류 계약은 [CreatePartition
문서](https://docs.aws.amazon.com/glue/latest/webapi/API_CreatePartition.html)처럼 operation별
공식 문서를 기준으로 작성합니다.

<!-- section: package -->
## Provider package 만들기

각 SPI는 서로 다른 entry-point namespace를 사용합니다. Python은 설치된 배포 package의
entry point를
[`importlib.metadata.entry_points`](https://docs.python.org/3/library/importlib.metadata.html#entry-points)로
찾습니다. Metadata 형식은 [PyPA entry point
명세](https://packaging.python.org/en/latest/specifications/entry-points/)를 따릅니다.

```toml
[project.entry-points."mystack.glue.extensions.stable.v1"]
my-correction = "my_extension:stable_provider"

[project.entry-points."mystack.glue.extensions.application.v1"]
my-application-extension = "my_extension:application_provider"

[project.entry-points."mystack.glue.extensions.unsafe.v1"]
my-unsafe-extension = "my_extension:unsafe_provider"
```

Entry point가 가리키는 callable은 해당 SPI context를 받아 `OperationMiddleware`를
반환합니다. 전체 예제는 `examples/glue-extension`에 있습니다. PyPA의 [plugin 탐색
안내](https://packaging.python.org/en/latest/guides/creating-and-discovering-plugins/)도 같은
방식을 설명합니다.

<!-- section: configuration -->
## YAML 설정

```yaml
glue:
  extensions:
    enabled: true
    allow_unsafe: true
    wheels_directory: /opt/mystack/extensions
    install_directory: /tmp/mystack/extensions
    install_timeout_seconds: 120
    providers:
      - id: my-stable-correction
        spi: stable
        api_version: 1
        entry_point: my-correction
        operations: [CreatePartition]
        priority: 100
        timeout_seconds: 5
      - id: my-application-extension
        spi: application
        api_version: 1
        entry_point: my-application-extension
        operations: [CreatePartition]
        priority: 200
        timeout_seconds: 5
        mystack_minor_version: "0.1"
      - id: my-unsafe-extension
        spi: unsafe
        api_version: 1
        entry_point: my-unsafe-extension
        operations: [CreatePartition]
        priority: 300
        timeout_seconds: 5
        mystack_version: 0.1.0
```

낮은 `priority`가 바깥 middleware가 됩니다. 같은 priority에서는 `id` 순서로
실행합니다. `operations: ["*"]`도 가능하지만 수정 범위를 검토하기 어려우므로 operation을
명시하는 방식을 권장합니다.

시작 단계는 중복 ID, 알 수 없는 operation, 지원하지 않는 API 버전, 누락된 entry point,
`application` 부 버전 불일치, 허용하지 않은 `unsafe`, 정확한 버전 불일치를 거부합니다.

<!-- section: docker -->
## Docker에서 실행하기

예제 wheel을 만들고 YAML의 `extensions`를 활성화합니다.

```bash
make extension-example
MYSTACK_GLUE_EXTENSIONS_DIR=./extensions \
docker compose \
  -f compose.yaml \
  -f compose.mount-config.yaml \
  -f compose.extensions.yaml \
  up --detach --wait
```

`compose.extensions.yaml`은 [Docker Compose volume
명세](https://docs.docker.com/reference/compose-file/services/#volumes)에 따라 directory를
읽기 전용으로 mount합니다. Container 시작 단계는 `.whl`만 찾습니다. `pip`에는
`--no-index --no-deps`를 사용하므로 network에서 dependency를 받거나 Mystack 기본 환경을
바꾸지 않습니다. 추가 dependency가 필요하면 해당 wheel도 같은 directory에 넣습니다.

`make extension-e2e`는 Docker Desktop의 host directory 공유 설정에 의존하지 않습니다.
작은 seed image가 [Docker volume의 초기 내용 복사
동작](https://docs.docker.com/engine/storage/volumes/#mounting-a-volume-over-existing-data)을
이용해 격리된 named volume을 채우고, Glue는 그 volume을 읽기 전용으로 mount합니다.

<!-- section: diagnostics -->
## 로그와 문제 해결

다음 event를 extension ID와 SPI 기준으로 검색합니다.

- `extension.install.*`: mount한 wheel 설치 전·후·실패
- `extension.provider.load.*`: entry point 탐색과 context 생성
- `extension.invoke.*`: operation별 실행 전·후·오류·제한 시간 초과
- `protocol.output_validation.failed`: plugin 또는 built-in handler의 잘못된 응답

로그에는 요청 본문 값, wheel 설치 출력, 인증 정보를 남기지 않습니다. `fix_hint`가 수정할
설정, entry point, provider, output mapper를 가리킵니다.

<!-- section: sources -->
## 공식 참고 자료

- [Python entry point 탐색](https://docs.python.org/3/library/importlib.metadata.html#entry-points)
- [PyPA plugin 탐색 안내](https://packaging.python.org/en/latest/guides/creating-and-discovering-plugins/)
- [PyPA entry point 명세](https://packaging.python.org/en/latest/specifications/entry-points/)
- [Docker Compose volume 명세](https://docs.docker.com/reference/compose-file/services/#volumes)
- [AWS Glue CreatePartition](https://docs.aws.amazon.com/glue/latest/webapi/API_CreatePartition.html)
- [AWS Hexagonal architecture 지침](https://docs.aws.amazon.com/prescriptive-guidance/latest/hexagonal-architectures/overview.html)
