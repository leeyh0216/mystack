<!-- doc-id: extending-proxy -->
<!-- lang: ko -->

[한국어](extending-proxy.ko.md) | [English](extending-proxy.md)

# Proxy 코드 변경 없이 새 에뮬레이터 추가

<!-- toc:start -->
## 목차

- [절차](#절차)
- [Protocol 변경과 서비스 변경](#protocol-변경과-서비스-변경)
<!-- toc:end -->

Proxy route registry는 공식 AWS request 근거인 `X-Amz-Target`, SigV4 credential-scope 서비스, 서비스 host prefix를 사용합니다. [Signature Version 4](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_sigv.html)와 [botocore 서비스 모델](https://github.com/boto/botocore/tree/develop/botocore/data)을 참고하세요.

<!-- section: procedure -->
## 절차

1. 공식 서비스 모델에서 `targetPrefix`, `endpointPrefix`, signing name, protocol, JSON/API version을 확인합니다.
2. 새 emulator를 독립 서비스로 만들고 Domain/Application/Adapter를 분리합니다.
3. YAML entry 하나를 추가합니다.

```yaml
proxy:
  routes:
    - name: athena
      backend_url: http://athena:8080
      target_prefixes: [AmazonAthena]
      signing_names: [athena]
      host_prefixes: [athena]
```

4. Internal network의 Compose 서비스를 추가하고 별도 공개 AWS port를 노출하지 않습니다.
5. Route detector 테스트와 Proxy를 통과하는 boto3 black-box 계약를 추가합니다.
6. 한글·영문 protocol, 범위, 설정, API 작업 범위 문서를 추가합니다.
7. 새 저장소, process, network, container side effect에 전·후·오류 로그를 추가합니다.

Proxy의 `if service == ...` 분기는 허용하지 않습니다. 중복 대상/signing/host claim은 시작 시 설정 검증에서 실패합니다.

<!-- section: evolution -->
## Protocol 변경과 서비스 변경

- 공통 AWS JSON 직렬화 변경은 `shared`
- 서비스별 요청·응답 구조 변환은 새 입력 어댑터
- 비즈니스 상태와 규칙은 Domain/Application
- Endpoint와 배포 값은 YAML 또는 deployment override만

클라이언트는 [공식 custom endpoint 방식](https://docs.aws.amazon.com/sdkref/latest/guide/feature-ss-endpoints.html)으로 같은 공개 URL을 선택합니다.
