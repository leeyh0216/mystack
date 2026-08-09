# syntax=docker/dockerfile:1.7
# Node official image and Vite production build references:
# https://hub.docker.com/_/node
# https://vite.dev/guide/build.html
ARG NODE_BASE=node:24.6.0-bookworm-slim@sha256:9b741b28148b0195d62fa456ed84dd6c953c1f17a3761f3e6e6797a754d9edff
ARG GLUE_BASE=public.ecr.aws/glue/aws-glue-libs:5@sha256:9a96a1097e7b992d8fb4e4430d01e6e797ddac26ff0ed405edbd0f3d71e426d7
FROM ${NODE_BASE} AS ui-builder
WORKDIR /workspace
COPY package.json package-lock.json ./
COPY ui/package.json ui/package.json
COPY emr/ui/package.json emr/ui/package.json
COPY glue/ui/package.json glue/ui/package.json
RUN npm ci --ignore-scripts
COPY ui ui
COPY glue/ui glue/ui
RUN npm run build --workspace @mystack/glue-ui

# SQLite's official WAL-reset guidance requires a fixed version at or above 3.51.3 for the
# multi-connection WAL use case. pysqlite3 builds against sqlite3.c/sqlite3.h when they are
# present in its source root, so this stage embeds the SHA-verified official amalgamation rather
# than replacing the AWS Glue image's global system library:
# https://www.sqlite.org/wal.html#the_wal_reset_bug
# https://github.com/coleifer/pysqlite3/blob/master/setup.py
FROM ${GLUE_BASE} AS sqlite-driver-builder
USER root
WORKDIR /opt/mystack/sqlite-build
COPY config/sqlite-runtime.json /opt/mystack/sqlite-build/sqlite-runtime.json
COPY glue/scripts/build_sqlite_driver.py /opt/mystack/sqlite-build/build_sqlite_driver.py
RUN dnf install --assumeyes --setopt=install_weak_deps=False gcc make python3-devel python3-setuptools \
    && python3 -c "import sysconfig; from pathlib import Path; header = Path(sysconfig.get_config_var('INCLUDEPY')) / 'Python.h'; assert header.is_file(), header" \
    && python3 /opt/mystack/sqlite-build/build_sqlite_driver.py \
      --config /opt/mystack/sqlite-build/sqlite-runtime.json \
      --output /opt/mystack/sqlite-driver \
    && dnf clean all \
    && rm -rf /var/cache/dnf /opt/mystack/sqlite-build

# AWS Glue 5.0 image/reference:
# https://docs.aws.amazon.com/glue/latest/dg/develop-local-docker-image.html
# PySpark interpreter selection:
# https://spark.apache.org/docs/3.5.4/configuration.html#environment-variables
FROM ${GLUE_BASE} AS final

ARG MYSTACK_VERSION=0.1.3
ARG MYSTACK_CONFIG_SOURCE=config/mystack.yaml
ARG GLUE_VERSION=5.0
ARG SPARK_VERSION=3.5.4
ARG ICEBERG_VERSION=1.7.1
LABEL org.opencontainers.image.title="Mystack Glue Data Catalog Emulator" \
      org.opencontainers.image.version="${MYSTACK_VERSION}" \
      org.opencontainers.image.source="https://github.com/leeyh0216/mystack" \
      org.opencontainers.image.glue.version="${GLUE_VERSION}" \
      org.opencontainers.image.spark.version="${SPARK_VERSION}" \
      org.opencontainers.image.iceberg.version="${ICEBERG_VERSION}"

USER root
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MYSTACK_CONFIG_FILE=/etc/mystack/mystack.yaml \
    MYSTACK_GLUE_SPARK_SUBMIT_BINARY=/usr/local/bin/spark-submit \
    PYSPARK_PYTHON=/opt/mystack/venv/bin/python \
    PYSPARK_DRIVER_PYTHON=/opt/mystack/venv/bin/python \
    PATH=/opt/mystack/bin:/opt/mystack/venv/bin:${PATH}

# This image implements only the Glue Data Catalog runtime documented by Mystack. AWS documents
# the base as a broad Glue job development image; crawler/job, Delta, Hudi, Flink, streaming,
# Redshift, and the root Maven cache are outside this image's supported catalog surface:
# https://docs.aws.amazon.com/glue/latest/dg/develop-local-docker-image.html
# https://docs.aws.amazon.com/glue/latest/dg/aws-glue-programming-etl-format-iceberg.html
RUN rm -rf \
      /root/.m2 \
      /usr/lib/hudi \
      /usr/local/lib/python3.11/site-packages/pyspark/jars \
      /usr/share/aws/delta \
      /usr/share/aws/glue-pds \
      /usr/share/aws/glue-streaming \
      /usr/share/aws/redshift \
    && rm -f \
      /usr/lib/spark/connector/lib/spark-streaming-kinesis-asl-assembly_2.12-3.5.4-amzn-0.jar \
      /usr/share/aws/iceberg/lib/iceberg-flink-runtime-1.20-1.7.1-amzn-1.jar \
      /usr/share/aws/iceberg/lib/iceberg-hive-runtime-1.7.1-amzn-1.jar

WORKDIR /opt/mystack
COPY requirements/glue.txt /opt/requirements.txt
COPY shared /opt/src/shared
COPY glue /opt/src/glue
COPY glue/bin/mystack-spark-submit /opt/mystack/bin/spark-submit
COPY --from=ui-builder /workspace/glue/src/mystack/glue/static/ui /opt/src/glue/src/mystack/glue/static/ui
COPY --from=sqlite-driver-builder /opt/mystack/sqlite-driver /opt/mystack/sqlite-driver
COPY ${MYSTACK_CONFIG_SOURCE} /etc/mystack/mystack.yaml
COPY glue/scripts/e2e /opt/mystack/e2e
RUN python3 -m venv /opt/mystack/venv \
    && /opt/mystack/venv/bin/python -m pip install --no-cache-dir \
      --require-hashes -r /opt/requirements.txt \
    && /opt/mystack/venv/bin/python -m pip install --no-cache-dir --no-deps \
      /opt/src/shared /opt/src/glue \
    && driver_site="$(/opt/mystack/venv/bin/python -c 'import site; print(site.getsitepackages()[0])')" \
    && cp -a /opt/mystack/sqlite-driver/pysqlite3 "$driver_site/pysqlite3" \
    && mkdir -p /opt/mystack/sqlite-runtime/licenses \
    && cp /opt/mystack/sqlite-driver/runtime-manifest.json /opt/mystack/sqlite-runtime/runtime-manifest.json \
    && cp /opt/mystack/sqlite-driver/licenses/pysqlite3-LICENSE /opt/mystack/sqlite-runtime/licenses/pysqlite3-LICENSE \
    && /opt/mystack/venv/bin/python -c "import json; import pysqlite3; from pathlib import Path; manifest = json.loads(Path('/opt/mystack/sqlite-runtime/runtime-manifest.json').read_text()); assert pysqlite3.sqlite_version == manifest['sqlite']['version'], pysqlite3.sqlite_version" \
    && rm -rf /opt/src /opt/requirements.txt \
    && rm -rf /opt/mystack/sqlite-driver \
    && chmod 0755 /opt/mystack/bin/spark-submit \
    && mkdir -p /var/lib/mystack/glue \
    && chown -R hadoop:hadoop /var/lib/mystack /opt/mystack

USER hadoop
EXPOSE 8080
ENTRYPOINT ["mystack-glue"]
CMD ["--config", "/etc/mystack/mystack.yaml"]
