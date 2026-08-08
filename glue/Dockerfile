# syntax=docker/dockerfile:1.7
# AWS Glue 5.0 image/reference:
# https://docs.aws.amazon.com/glue/latest/dg/develop-local-docker-image.html
ARG GLUE_BASE=public.ecr.aws/glue/aws-glue-libs:5@sha256:9a96a1097e7b992d8fb4e4430d01e6e797ddac26ff0ed405edbd0f3d71e426d7
FROM ${GLUE_BASE}

ARG MYSTACK_VERSION=0.1.0
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
    PATH=/opt/mystack/venv/bin:${PATH}

WORKDIR /opt/mystack
COPY requirements/glue.txt /opt/requirements.txt
COPY shared /opt/src/shared
COPY glue /opt/src/glue
COPY ${MYSTACK_CONFIG_SOURCE} /etc/mystack/mystack.yaml
COPY glue/scripts/e2e /opt/mystack/e2e
COPY glue/scripts/extension-entrypoint.sh /opt/mystack/extension-entrypoint
RUN python3 -m venv /opt/mystack/venv \
    && /opt/mystack/venv/bin/python -m pip install --no-cache-dir \
      --require-hashes -r /opt/requirements.txt \
    && /opt/mystack/venv/bin/python -m pip install --no-cache-dir --no-deps \
      /opt/src/shared /opt/src/glue \
    && rm -rf /opt/src /opt/requirements.txt \
    && chmod 0755 /opt/mystack/extension-entrypoint \
    && mkdir -p /var/lib/mystack/glue /opt/mystack/extensions \
    && chown -R hadoop:hadoop /var/lib/mystack /opt/mystack

USER hadoop
EXPOSE 8080
ENTRYPOINT ["/opt/mystack/extension-entrypoint"]
CMD ["--config", "/etc/mystack/mystack.yaml"]
