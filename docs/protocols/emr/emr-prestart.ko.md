<!-- doc-id: emr-prestart -->
<!-- lang: ko -->

[한국어](emr-prestart.ko.md) | [English](emr-prestart.md)

# Mystack 시작 전에 EMR image 구성하기

<!-- toc:start -->
## 목차

- [검토한 script로 게시 image 시작하기](#검토한-script로-게시-image-시작하기)
- [실행 순서와 사용자 계약](#실행-순서와-사용자-계약)
- [신뢰 경계와 file 검사](#신뢰-경계와-file-검사)
- [인증서, proxy, Python과 Java](#인증서-proxy-python과-java)
- [추측 대신 image 정보 확인하기](#추측-대신-image-정보-확인하기)
- [안전하게 시작 실패 진단하기](#안전하게-시작-실패-진단하기)
- [지원 범위](#지원-범위)
- [공식 참고 자료](#공식-참고-자료)
<!-- toc:end -->

게시한 EMR image에 enterprise CA 인증서, proxy 환경변수 또는 machine 수준 선행 구성이 필요할 때
이 운영자 전용 hook을 사용하세요. EMR service, bootstrap action과 Spark Step보다 먼저 실행합니다.
기본값은 비활성이며 EMR container에만 적용됩니다.

<!-- section: quick-start -->
## 검토한 script로 게시 image 시작하기

같은 release tag에서 기본 Compose file, overlay와 예제 script를 받으세요. 시작 전에 placeholder
인증서 경로를 교체해야 합니다. Directory는 Docker의 [bind mount
계약](https://docs.docker.com/engine/storage/bind-mounts/)에 따라 read-only로 mount합니다.

```bash
export MYSTACK_IMAGE_TAG=v0.1.5  # 실제 게시 tag로 교체
mkdir -p mystack-runtime/emr-prestart.d && cd mystack-runtime
for path in compose.ghcr.yaml compose.emr-prestart.yaml; do
  gh api -H "Accept: application/vnd.github.raw+json" \
    "repos/leeyh0216/mystack/contents/${path}?ref=${MYSTACK_IMAGE_TAG}" > "${path}"
done
for path in 10-enterprise-ca.sh 20-proxy-environment.sh; do
  gh api -H "Accept: application/vnd.github.raw+json" \
    "repos/leeyh0216/mystack/contents/examples/emr-prestart/${path}?ref=${MYSTACK_IMAGE_TAG}" \
    > "emr-prestart.d/${path}"
done
chmod 0755 emr-prestart.d
chmod 0644 emr-prestart.d/*.sh
export MYSTACK_EMR_PRESTART_SOURCE="$PWD/emr-prestart.d"
docker compose -f compose.ghcr.yaml -f compose.emr-prestart.yaml config --quiet
docker compose -f compose.ghcr.yaml -f compose.emr-prestart.yaml up --detach --wait --wait-timeout 300
```

예제는 template이며 안전한 기본 설정이 아닙니다. `10-enterprise-ca.sh`는 운영자가 관리하는
인증서가 설정 경로에 없으면 의도적으로 실패합니다. Secret, AWS credential, 내려받은 workload
file이나 검토하지 않은 script를 이 directory에 두지 마세요.

<!-- section: lifecycle -->
## 실행 순서와 사용자 계약

Container entrypoint는 `root`로 시작해 byte 기준 file 이름 순서로 `*.sh`를 한 번 찾고 같은 shell에서
각 script를 source합니다. 하나라도 0이 아닌 값으로 끝나면 container를 즉시 중지하며 뒤 script와
EMR service를 실행하지 않습니다. 따라서 export한 환경변수는 EMR API process, `hadoop` bootstrap
child와 Spark child까지 전달됩니다. Export하지 않은 shell 변수는 전달되지 않습니다.

모든 script가 성공하면 entrypoint는 작업 directory와 안전한 field separator를 복원하고
`HOME=/home/hadoop`을 설정합니다. 그다음 보조 group, GID와 UID를 고정 `hadoop` account로 바꾸고
설정한 명령으로 PID 1을 교체합니다. 이 방식은 Docker의 [exec 형식 ENTRYPOINT signal
동작](https://docs.docker.com/reference/dockerfile/#entrypoint)과 Python의
[`setuid`](https://docs.python.org/3.11/library/os.html#os.setuid) 계약을 따릅니다. Amazon EMR의
일반 [bootstrap action은 Hadoop 사용자로 실행하며 root 작업에 `sudo`를
사용](https://docs.aws.amazon.com/emr/latest/ManagementGuide/emr-plan-bootstrap.html)합니다. Pre-start
hook은 image 초기화 경계이며 EMR `BootstrapActions` API entry가 아닙니다.

EMR container user를 override하지 마세요. 일반 진단은
`docker compose exec --user hadoop emr ...`를 사용하고, 의도한 운영자 진단에만 root를 사용하세요.

<!-- section: trust -->
## 신뢰 경계와 file 검사

Hook을 활성화하면 허용된 모든 script에 임의 root 실행 권한을 부여합니다. Mystack은 없거나 symlink인
directory, group 또는 다른 사용자가 쓸 수 있는 directory, 안전하지 않은 이름, symlink, 일반 file이
아닌 entry, group 또는 다른 사용자가 쓸 수 있는 script를 거부합니다. Source 방식이므로 executable
bit는 필요하지 않습니다. 이 검사는 우발적인 바꿔치기를 줄이지만 신뢰한 root code를 sandbox하지는
않습니다.

다음 값은 Python 설정을 읽기 전에 처리해야 하므로 application YAML이 아닌 entrypoint 환경변수입니다.

| 이름 | 기본값 | 의미 |
| --- | --- | --- |
| `MYSTACK_EMR_PRESTART_ENABLED` | `false` | 명시적 활성화 boolean |
| `MYSTACK_EMR_PRESTART_DIR` | `/etc/mystack/emr-prestart.d` | Container 안의 검토된 directory |
| `MYSTACK_EMR_PRESTART_SOURCE` | 없음 | Compose overlay가 요구하는 host directory |

`10-ca.sh`, `20-environment.sh`처럼 안정적인 숫자 prefix를 사용하세요. Mount한 file을 바꾸면 container를
다시 만들어야 합니다. Hook은 의도적으로 hot reload하지 않습니다.

<!-- section: certificates -->
## 인증서, proxy, Python과 Java

Enterprise CA는 검토한 PEM 인증서를 `/etc/pki/ca-trust/source/anchors`에 복사하고
`update-ca-trust extract`를 실행하세요. Client가 명시적 경로를 요구하면 `SSL_CERT_FILE`,
`REQUESTS_CA_BUNDLE`, `AWS_CA_BUNDLE`을 설정합니다. Java에는 공식 [Java 17 `keytool`
interface](https://docs.oracle.com/en/java/javase/17/docs/specs/man/keytool.html)로 import합니다. System
Java store를 직접 바꾸고 싶지 않다면 복사한 운영자 소유 truststore와
`JAVA_TOOL_OPTIONS=-Djavax.net.ssl.trustStore=...` 사용을 권장합니다.

`HTTP_PROXY`, `HTTPS_PROXY`, `NO_PROXY`는 container network에 맞는 값만 설정하세요. Emulator
traffic이 Docker network 밖으로 나가지 않도록 `NO_PROXY`에 `proxy`, `emr`, `glue`, `localstack`,
loopback 이름과 필요한 내부 domain을 넣으세요.

Python 3.11, `venv`, Java 17, `keytool`, Spark 3.5.4, AWS CLI와 기본 trust path는 이미 설치되어
있습니다. Bootstrap에서 만든 virtualenv는 `hadoop`이 소유하거나 읽을 수 있어야 합니다. 뒤 Step은
`spark.pyspark.python`과 `spark.pyspark.driver.python`으로 이를 명시적으로 선택해야 합니다.
Python [`venv` 문서](https://docs.python.org/3.11/library/venv.html)는 interpreter 경로를 직접 고르면
shell activation이 필요하지 않은 이유를 설명합니다.

<!-- section: inventory -->
## 추측 대신 image 정보 확인하기

모든 image에는 build 시점 정보가 `/opt/mystack/runtime-inventory.json`에 포함됩니다. 실행 중인
container에서 환경변수 값을 출력하지 않고 같은 schema를 만들 수 있습니다.

```bash
docker compose -f compose.ghcr.yaml exec --user hadoop emr mystack-emr-runtime-inventory
docker compose -f compose.ghcr.yaml exec --user hadoop emr \
  python3.11 -m venv /home/hadoop/example-venv
docker compose -f compose.ghcr.yaml exec --user hadoop emr \
  keytool -list -cacerts -storepass changeit
```

이 정보는 실제 base OS, service UID/GID/home, 확인된 실행 file과 version, Python package와 CA
path, Spark home/release/Ivy directory, 쓰기 가능한 path, 인식하는 환경변수 이름을 기록합니다.
환경변수 값은 기록하지 않습니다. `process_tools.ps`는 반드시 실제 path여야 합니다. Spark의
[`bin/load-spark-env.sh`](https://github.com/apache/spark/blob/v3.5.4/bin/load-spark-env.sh)가
기존 process를 찾을 때 `ps`를 호출하므로 image가 Amazon Linux `procps-ng`를 설치합니다. Null
path는 무시할 warning이 아니라 image 계약 실패입니다.

<!-- section: diagnostics -->
## 안전하게 시작 실패 진단하기

`docker compose logs emr`에는 구조화된 `emr.prestart.scan.*`,
`emr.prestart.script.before`, `emr.prestart.script.after`, `emr.prestart.script.failed` event가
남습니다. Basename, 권한과 소유자 정보, SHA-256 prefix, 실행 시간 또는 exit code, 수정 위치만
포함하며 script 내용과 환경변수 값은 기록하지 않습니다. 바뀐 fingerprint로 향후 image, SDK,
Java 또는 Spark 갱신 뒤 문제가 생긴 file을 찾을 수 있습니다.

Service가 시작하지 않으면 첫 failure event를 읽고 해당 script를 고친 뒤 container를 다시 만드세요.
Bootstrap 또는 Spark가 값을 받지 못하면 script에 `export`가 있는지 확인하세요. 전체 환경을 출력하지
않는 방식으로 root가 PID 1을 검사할 수 있습니다. Compose wait와 모든 자동 진단 명령에는 명시적인
제한 시간을 유지하세요.

<!-- section: scope -->
## 지원 범위

검증 범위는 EMR service 전 한 번 실행하는 신뢰된 lexical order source, 즉시 실패 중단, 권한 전환을
통과한 환경 전달, 최종 `hadoop` 사용자, signal-safe PID 1 교체, runtime 정보와 게시 GHCR image의
Docker Compose 사용입니다. 동적 reload, cluster별 hook, 신뢰하지 않은 plugin, secret 관리, host
변경과 Glue image 초기화는 이 기능 범위가 아닙니다.

<!-- section: sources -->
## 공식 참고 자료

- [Docker bind mount](https://docs.docker.com/engine/storage/bind-mounts/)
- [Docker ENTRYPOINT](https://docs.docker.com/reference/dockerfile/#entrypoint)
- [Amazon EMR bootstrap action](https://docs.aws.amazon.com/emr/latest/ManagementGuide/emr-plan-bootstrap.html)
- [Java 17 keytool](https://docs.oracle.com/en/java/javase/17/docs/specs/man/keytool.html)
- [Python venv](https://docs.python.org/3.11/library/venv.html)
- [Python setuid](https://docs.python.org/3.11/library/os.html#os.setuid)
