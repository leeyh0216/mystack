# syntax=docker/dockerfile:1.7
# Node official image and Vite production build references:
# https://hub.docker.com/_/node
# https://vite.dev/guide/build.html
ARG NODE_BASE=node:24.6.0-bookworm-slim@sha256:9b741b28148b0195d62fa456ed84dd6c953c1f17a3761f3e6e6797a754d9edff
ARG AMAZON_LINUX_BASE=public.ecr.aws/amazonlinux/amazonlinux:2023@sha256:6d8e068b91f351df5bf6acd4bd261316e42747ad4bae76689ff6f4939e2180a2
FROM ${NODE_BASE} AS ui-builder
WORKDIR /workspace
COPY package.json package-lock.json ./
COPY ui/package.json ui/package.json
COPY emr/ui/package.json emr/ui/package.json
COPY glue/ui/package.json glue/ui/package.json
RUN npm ci --ignore-scripts
COPY ui ui
COPY emr/ui emr/ui
RUN npm run build --workspace @mystack/emr-ui

# Amazon Linux public ECR source: https://gallery.ecr.aws/amazonlinux/amazonlinux
FROM ${AMAZON_LINUX_BASE} AS runtime-base

ARG SPARK_VERSION=3.5.4
ARG SPARK_DISTRIBUTION=hadoop3
ARG SPARK_ARCHIVE_BASE_URL=https://archive.apache.org/dist/spark
ARG AWS_CLI_VERSION=2.27.41
ARG TARGETARCH
ARG MYSTACK_VERSION=0.1.3
ARG MYSTACK_CONFIG_SOURCE=config/mystack.yaml
LABEL org.opencontainers.image.title="Mystack EMR Spark Emulator" \
      org.opencontainers.image.version="${MYSTACK_VERSION}" \
      org.opencontainers.image.source="https://github.com/leeyh0216/mystack" \
      org.opencontainers.image.spark.version="${SPARK_VERSION}"

# Corretto package reference:
# https://docs.aws.amazon.com/corretto/latest/corretto-17-ug/amazon-linux-install.html
# Spark's official load-spark-env script calls ps while locating running processes:
# https://github.com/apache/spark/blob/v3.5.4/bin/load-spark-env.sh
RUN dnf install -y \
      gzip \
      java-17-amazon-corretto-headless \
      python3.11 \
      python3.11-pip \
      procps-ng \
      shadow-utils \
      sudo \
      tar \
      unzip \
    && dnf clean all

# Spark release reference: https://spark.apache.org/releases/spark-release-3-5-4.html
RUN archive="spark-${SPARK_VERSION}-bin-${SPARK_DISTRIBUTION}.tgz" \
    && curl --fail --location --retry 5 \
      "${SPARK_ARCHIVE_BASE_URL}/spark-${SPARK_VERSION}/${archive}" \
      --output "/tmp/${archive}" \
    && curl --fail --location --retry 5 \
      "${SPARK_ARCHIVE_BASE_URL}/spark-${SPARK_VERSION}/${archive}.sha512" \
      --output "/tmp/${archive}.sha512" \
    && cd /tmp \
    && sha512sum --check "${archive}.sha512" \
    && mkdir -p /opt/spark \
    && tar --extract --gzip --file "/tmp/${archive}" --strip-components=1 --directory /opt/spark \
    && rm -f "/tmp/${archive}" "/tmp/${archive}.sha512"

# Pinned AWS CLI installer and architecture mapping follow the official install guide:
# https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html
RUN case "${TARGETARCH}" in \
      amd64) cli_arch=x86_64 ;; \
      arm64) cli_arch=aarch64 ;; \
      *) echo "Unsupported TARGETARCH=${TARGETARCH}" >&2; exit 1 ;; \
    esac \
    && curl --fail --location --retry 5 \
      "https://awscli.amazonaws.com/awscli-exe-linux-${cli_arch}-${AWS_CLI_VERSION}.zip" \
      --output /tmp/awscliv2.zip \
    && unzip -q /tmp/awscliv2.zip -d /tmp \
    && /tmp/aws/install \
    && rm -rf /tmp/aws /tmp/awscliv2.zip

FROM runtime-base AS jar-builder
RUN dnf install -y java-17-amazon-corretto-devel \
    && dnf clean all
COPY emr/scripts/e2e/SparkS3JarJob.java /tmp/mystack-e2e/SparkS3JarJob.java
RUN mkdir -p /tmp/mystack-e2e/classes \
    && javac -cp '/opt/spark/jars/*' \
      -d /tmp/mystack-e2e/classes /tmp/mystack-e2e/SparkS3JarJob.java \
    && jar --create \
      --file /tmp/mystack-e2e/spark-s3-job.jar \
      --main-class mystack.e2e.SparkS3JarJob \
      -C /tmp/mystack-e2e/classes .

FROM runtime-base AS final
ARG MYSTACK_CONFIG_SOURCE=config/mystack.yaml

ENV JAVA_HOME=/usr/lib/jvm/jre-17 \
    SPARK_HOME=/opt/spark \
    PATH=/opt/spark/bin:/usr/local/bin:/usr/local/sbin:/usr/bin:/usr/sbin:/bin:/sbin \
    PYSPARK_PYTHON=python3.11 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MYSTACK_CONFIG_FILE=/etc/mystack/mystack.yaml

WORKDIR /opt/mystack
COPY --from=jar-builder /tmp/mystack-e2e/spark-s3-job.jar /opt/mystack/spark-s3-job.jar
COPY requirements/emr.txt /opt/requirements.txt
RUN python3.11 -m pip install --no-cache-dir --require-hashes -r /opt/requirements.txt
COPY shared /opt/src/shared
COPY emr /opt/src/emr
COPY --from=ui-builder /workspace/emr/src/mystack/emr/static/ui /opt/src/emr/src/mystack/emr/static/ui
COPY ${MYSTACK_CONFIG_SOURCE} /etc/mystack/mystack.yaml
COPY --chmod=0755 emr/scripts/container/entrypoint.sh /usr/local/bin/mystack-emr-entrypoint
# EMR bootstrap actions run as hadoop and use sudo for privileged work:
# https://docs.aws.amazon.com/emr/latest/ManagementGuide/emr-plan-bootstrap.html
RUN python3.11 -m pip install --no-cache-dir --no-deps /opt/src/shared /opt/src/emr \
    && rm -rf /opt/src /opt/requirements.txt \
    && useradd --create-home --uid 10001 hadoop \
    && mkdir -p \
      /var/lib/mystack/emr \
      /home/hadoop/.ivy2 \
      /etc/mystack/emr-prestart.d \
      /etc/sudoers.d \
    && printf 'hadoop ALL=(ALL) NOPASSWD: ALL\n' > /etc/sudoers.d/hadoop \
    && chmod 0440 /etc/sudoers.d/hadoop \
    && chown -R hadoop:hadoop /var/lib/mystack /home/hadoop \
    && mystack-emr-runtime-inventory --output /opt/mystack/runtime-inventory.json \
    && chmod 0444 /opt/mystack/runtime-inventory.json

EXPOSE 8080
ENTRYPOINT ["/usr/local/bin/mystack-emr-entrypoint"]
CMD ["--config", "/etc/mystack/mystack.yaml"]
