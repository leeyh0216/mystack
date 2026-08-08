<!-- doc-id: adr-0003-pep420-namespace-packages -->
<!-- lang: ko -->

[한국어](0003-pep420-namespace-packages.ko.md) | [English](0003-pep420-namespace-packages.md)

# ADR-0003: Python distribution을 PEP 420 namespace로 합성

<!-- section: status -->
## 상태

2026-08-08에 채택했습니다. 기존 최상위 import package인 `mystack_aws_protocol`,
`mystack_proxy`, `mystack_emr`, `mystack_glue`를 이 결정으로 교체합니다.

<!-- section: context -->
## 배경

Mystack은 독립적으로 build하는 Python distribution 네 개를 게시하지만 하나의 제품입니다.
서로 다른 최상위 import 이름은 같은 제품의 소유 관계를 드러내지 못하고 새 service가 관련 없는
전역 이름을 계속 추가하기 쉽습니다. Python은 여러 distribution이 일부를 제공하는 implicit
namespace package를 정의하며 uv build backend는 이 구조에 dotted module 이름을 지원합니다.

<!-- section: decision -->
## 결정

Distribution 이름은 유지하고 다음 import 경로를 사용합니다.

| Distribution | Import package |
| --- | --- |
| `mystack-aws-protocol` | `mystack.aws_protocol` |
| `mystack-proxy` | `mystack.proxy` |
| `mystack-emr` | `mystack.emr` |
| `mystack-glue` | `mystack.glue` |

어떤 distribution도 `mystack/__init__.py`를 포함할 수 없습니다. 각 member는 dotted
`tool.uv.build-backend.module-name`을 선언하고 console script는 새 module을 직접 가리킵니다.
이 Python package는 repository 내부에서만 사용하므로 compatibility shim은 제공하지 않습니다.

<!-- section: consequences -->
## 결과

담당 영역 사이의 결합을 추가하지 않으면서 모든 제품 module의 공통 소유 관계가 드러납니다.
새 distribution도 `mystack.<service>` 일부를 제공할 수 있습니다. Wheel 하나가 namespace root
initializer를 추가하면 함께 설치할 때 조용히 깨질 수 있으므로 source tree import만으로는
충분히 검증할 수 없습니다.

<!-- section: verification -->
## 검증

`make package-check`는 모든 workspace distribution을 build하고 각 wheel을 검사한 뒤 임시 virtual
environment에 함께 설치해 설정된 module을 모두 찾습니다. Subprocess 제한 시간은
`tests.package_smoke_timeout_seconds`에서 읽습니다. Architecture test도 namespace root initializer를
거부하고 module 경로가 각 member의 build 설정과 일치하는지 확인합니다.

<!-- section: sources -->
## 공식 참고 자료

- [Python namespace package 명세](https://docs.python.org/3/reference/import.html#namespace-packages)
- [Python virtual environment](https://docs.python.org/3/library/venv.html)
- [uv namespace package 설정](https://docs.astral.sh/uv/concepts/build-backend/#namespace-packages)
