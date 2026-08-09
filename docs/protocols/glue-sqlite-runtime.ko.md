<!-- doc-id: protocols/glue-sqlite-runtime -->
<!-- lang: ko -->

[한국어](glue-sqlite-runtime.ko.md) | [English](glue-sqlite-runtime.md)

# Glue SQLite runtime 계약

<!-- toc:start -->
## 목차

- [목차](#목차)
- [Runtime 경계](#runtime-경계)
- [설정](#설정)
- [시작 검증](#시작-검증)
- [저장소 운영](#저장소-운영)
- [관측과 수정 위치](#관측과-수정-위치)
- [공식 참고 자료](#공식-참고-자료)
<!-- toc:end -->

<!-- section: index -->
## 목차

- [Runtime 경계](#runtime-경계)
- [설정](#설정)
- [시작 검증](#시작-검증)
- [저장소 운영](#저장소-운영)
- [관측과 수정 위치](#관측과-수정-위치)

<!-- section: boundary -->
## Runtime 경계

Glue image는 `config/sqlite-runtime.json`에 고정한 SHA 검증 공식 SQLite amalgamation으로 target OCI
architecture마다 `pysqlite3`를 별도 build합니다. 이 private DB-API module은
`/opt/mystack/venv`에만 설치합니다. AWS Glue base image의 global SQLite library는 바꾸지 않습니다.
생성한 runtime manifest에는 SQLite version, architecture, source digest를 기록합니다.

WAL이 기본값입니다. SQLite는 concurrent connection이 WAL database를 write하거나 checkpoint할 때
3.51.2 이하 version에 corruption race가 있음을 문서화합니다. Mystack은 3.51.3 이상을 요구하고
unsafe runtime이면 Glue가 catalog를 초기화하기 전에 시작을 거부합니다.

이 계약은 DB-API runtime과 filesystem capability만 검증합니다. Catalog persistence를 선택하거나
migration하지 않습니다. 실행 중인 Glue application은 계속 `glue.state_file`의
`JsonCatalogRepository`를 조립합니다. `glue.sqlite.database_file`은 생성 후 삭제하는 임시 runtime
probe의 directory만 선택합니다. 이후 SQLite catalog persistence adapter는 별도 변경으로 state
migration과 recovery 계약을 정의해야 합니다.

<!-- section: configuration -->
## 설정

`glue.sqlite`는 `config/mystack.yaml`의 일부입니다. 상대 `database_file` path는
`glue.data_root` 아래에서 해석합니다. 상대 driver manifest path는 mount한 YAML file 옆에서
해석합니다.

```yaml
glue:
  sqlite:
    database_file: catalog.sqlite3
    driver:
      module: pysqlite3.dbapi2
      expected_version: "3.53.4"
      minimum_wal_version: "3.51.3"
      manifest_file: /opt/mystack/sqlite-runtime/runtime-manifest.json
    journal_mode: wal
    synchronous: normal
    busy_timeout_milliseconds: 5000
    retry_limit: 3
    checkpoint:
      mode: passive
      auto_checkpoint_pages: 1000
```

`journal_mode`에는 `wal` 또는 `rollback`을 지정합니다. `rollback`은 SQLite의 명시적 `DELETE`
journal mode로 변환하며 자동 fallback으로 선택하지 않습니다. `synchronous`에는 `off`, `normal`,
`full`, `extra`를 지정합니다. `checkpoint.mode`에는 `passive`, `full`, `restart`, `truncate`를
지정합니다. 이후 SQLite catalog adapter는 이 policy로 controlled checkpoint를 수행합니다.
`retry_limit`은 같은 adapter의 상한이 있는 `SQLITE_BUSY` retry에 사용합니다.

현재 runtime 전용 단계에서 `database_file`은 catalog database가 아닙니다. Verifier가 그 parent에
격리된 `.mystack-sqlite-probe-*` database와 WAL sibling을 만들고 삭제하므로 write 가능해야 합니다.
영속 Glue catalog state는 계속 `glue.state_file`과 설정한 lock file에 둡니다.

<!-- section: verification -->
## 시작 검증

Catalog 초기화 전에 Glue process는 선택한 driver module, 보고한 SQLite version, WAL build manifest,
쓰기가 가능한 database directory, foreign key, `busy_timeout`, `synchronous`, 선택한 journal mode,
WAL sibling file 생성을 검사합니다. WAL 요청의 driver, version, manifest, PRAGMA 결과 중 하나라도
다르면 시작을 거부합니다. Mystack은 journal mode를 조용히 바꾸지 않습니다.

HTTP를 시작하지 않고 같은 검증을 실행합니다.

```bash
mystack-glue --config /etc/mystack/mystack.yaml --verify-sqlite-runtime
```

Command는 driver module, SQLite version, 선택한 journal mode, 검증한 PRAGMA를 담은 JSON document
하나를 출력합니다. Glue image release preflight는 `linux/amd64`, `linux/arm64` image 모두에서 이
command를 실행합니다.

<!-- section: operations -->
## 저장소 운영

Runtime verifier에는 database 하나가 아닌 write 가능한 directory 전체를 mount합니다. Verifier는
임시 probe와 `-wal`, `-shm` sibling을 만들고 삭제합니다. 이 동작은 `catalog.sqlite3`을 영속
catalog storage로 만들지 않습니다. 이후 SQLite catalog adapter가 WAL을 사용할 때는
`catalog.sqlite3` 하나가 아니라 database directory 전체를 mount하거나 유지해야 합니다. 하나의 WAL
database에 접근하는 모든 Glue process는 같은 host에서 같은 mounted directory를 사용해야 합니다.
Network filesystem은 지원하는 WAL deployment가 아닙니다.

Filesystem level backup을 만들 때는 database를 사용하는 모든 Glue process를 멈춘 뒤 directory
전체를 복사합니다. Online backup에는 SQLite backup API를 사용합니다. Maintenance checkpoint가
필요하면 설정한 checkpoint mode를 실행하고 file을 복사하기 전에 `SQLITE_BUSY`가 없었는지
확인합니다. Live database file을 `-wal` sibling과 분리해 복사하지 않습니다.

의도적으로 rollback을 선택하려면 mounted configuration을 바꾸고 Glue를 restart합니다.

```yaml
glue:
  sqlite:
    journal_mode: rollback
    driver:
      module: sqlite3
```

이 선택은 runtime verification 출력의 `manifest_verified: false`로 확인합니다. Operator가
rollback-journal concurrency 특성을 의도적으로 수용할 때만 사용합니다. Mystack이 스스로 선택하는
recovery 경로가 아닙니다.

<!-- section: observability -->
## 관측과 수정 위치

`glue.sqlite.runtime.verify.before`, `.after`, `.failed` event는 선택한 driver module, journal mode,
SQLite version, timeout, checkpoint policy, repair hint를 기록합니다. Source URL, credential,
database content, request payload는 기록하지 않습니다. Health endpoint
`/_mystack/health`는 `sqlite_runtime`에 검증한 runtime document를 제공합니다.

새 base image 또는 Python runtime으로 이 경계가 깨지면 다음 순서로 확인합니다.

1. Source version, URL 형태, checksum: `config/sqlite-runtime.json`
2. 검증, extraction, extension compilation: `glue/scripts/build_sqlite_driver.py`
3. Active Python ABI header 선택: `glue/scripts/install_python_build_dependencies.py`
4. Private virtualenv 설치 경계: `glue/Dockerfile`
5. 시작 capability 검사: `glue/src/mystack/glue/adapters/outbound/sqlite_runtime.py`
6. Mounted policy parsing: `config/mystack.yaml`, `glue/src/mystack/glue/config.py`

<!-- section: sources -->
## 공식 참고 자료

- [SQLite WAL](https://www.sqlite.org/wal.html)
- [SQLite PRAGMA reference](https://www.sqlite.org/pragma.html)
- [SQLite download and checksum format](https://www.sqlite.org/download.html)
- [AWS Glue local Docker image](https://docs.aws.amazon.com/glue/latest/dg/develop-local-docker-image.html)
- [pysqlite3 source build logic](https://github.com/coleifer/pysqlite3/blob/master/setup.py)
