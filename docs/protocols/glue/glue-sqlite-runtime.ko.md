<!-- doc-id: protocols/glue/glue-sqlite-runtime -->
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

검증한 DB-API runtime은 Mystack의 유일한 영속 Glue catalog을 구동합니다. 검증이 성공하면 Glue
application은 `glue.sqlite.database_file`에 정규화된 SQLite schema를 초기화합니다. Model에 없는
field를 보존해야 하는 Glue request document는 canonical JSON `TEXT`로 유지하되 database, table,
archive version, partition, optimizer, optimizer run 식별자는 foreign key를 갖는 관계형 row로
저장합니다. 따라서 database/table rename은 parent row만 바꾸고 delete cascade는 원자적으로
처리됩니다.

JSON catalog fallback이나 migration 경로는 없습니다. 이전에 `glue.state_file`을 사용했다면 설정한
SQLite catalog file로 새로 시작해야 합니다. Mystack은 legacy JSON state document를 조용히 import,
사용 또는 overwrite하지 않습니다.

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

`database_file`은 영속 catalog database입니다. 그 **parent directory**를 write 가능하게 mount해야
합니다. WAL은 `catalog.sqlite3` 옆에 영속 `catalog.sqlite3-wal`, `catalog.sqlite3-shm` sibling을
만듭니다. `journal_mode`에는 `wal` 또는 `rollback`을 지정하며, `rollback`은 SQLite의 명시적
`DELETE` journal mode로 변환되고 자동으로 선택되지 않습니다. `synchronous`에는 `off`, `normal`,
`full`, `extra`를 지정합니다. `busy_timeout_milliseconds`는 DB-API wait 상한이고 `retry_limit`은
writer 경합 시 application의 상한 있는 retry 횟수입니다. `checkpoint.mode`에는 `passive`, `full`,
`restart`, `truncate`를 지정하며 `auto_checkpoint_pages`는 SQLite 자동 WAL checkpoint threshold입니다.

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

`catalog.sqlite3` 하나가 아니라 write 가능한 directory 전체를 mount합니다. 시작 verifier는 schema
초기화 전에 같은 directory에 격리된 probe와 `-wal`, `-shm` sibling을 만들고 지웁니다. 그 뒤 catalog은
database와 `-wal`, `-shm` sibling을 같은 directory에 유지합니다. 하나의 WAL database에 접근하는 모든
Glue process는 같은 host에서 같은 mounted directory를 사용해야 합니다. Network filesystem은 지원하는
WAL deployment가 아닙니다.

Catalog mutation은 짧은 `BEGIN IMMEDIATE` transaction을 시작하고 application 소유 domain 판단,
정규화 row의 조건부 update, 진단용 catalog revision 증가, commit 순서로 실행합니다. SQLite는 writer
하나를 허용하며 reader는 별도 short-lived connection을 사용합니다. Writer가 busy이면
`busy_timeout_milliseconds`만큼 기다린 뒤 `retry_limit` 횟수까지만 재시도하며, 그 뒤에는 partial
change 없이 요청이 실패합니다. Adapter는 진행 중인 commit을 task cancellation으로부터 보호한 뒤
commit/rollback 결과를 보고합니다.

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
SQLite version, timeout, checkpoint policy, repair hint를 기록합니다.
`glue.sqlite_catalog.schema.*`, `glue.sqlite_catalog.transaction.*`은 schema 시작, 상한 있는 busy
retry, commit/rollback, duration, resource fingerprint도 기록합니다. Source URL, credential,
database content, request payload는 기록하지 않습니다. Health endpoint `/_mystack/health`는
`sqlite_runtime`에 검증한 runtime document를 제공합니다.

새 base image 또는 Python runtime으로 이 경계가 깨지면 다음 순서로 확인합니다.

1. Source version, URL 형태, checksum: `config/sqlite-runtime.json`
2. 검증, extraction, extension compilation: `glue/scripts/build_sqlite_driver.py`
3. Active Python ABI header 선택: `glue/scripts/install_python_build_dependencies.py`
4. Private virtualenv 설치 경계: `glue/Dockerfile`
5. 시작 capability 검사: `glue/src/mystack/glue/adapters/outbound/sqlite_runtime.py`
6. Schema, mapping, connection, transaction: `glue/src/mystack/glue/adapters/outbound/sqlite_catalog/`
7. Mounted policy parsing: `config/mystack.yaml`, `glue/src/mystack/glue/config.py`

<!-- section: sources -->
## 공식 참고 자료

- [SQLite WAL](https://www.sqlite.org/wal.html)
- [SQLite PRAGMA reference](https://www.sqlite.org/pragma.html)
- [SQLite download and checksum format](https://www.sqlite.org/download.html)
- [AWS Glue local Docker image](https://docs.aws.amazon.com/glue/latest/dg/develop-local-docker-image.html)
- [pysqlite3 source build logic](https://github.com/coleifer/pysqlite3/blob/master/setup.py)
