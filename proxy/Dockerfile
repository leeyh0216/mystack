# syntax=docker/dockerfile:1.7
# Official Python image mirror: https://gallery.ecr.aws/docker/library/python
ARG PYTHON_BASE=public.ecr.aws/docker/library/python:3.11-slim-bookworm@sha256:d29f48a31a8b408ed19272ca1e7b10ebae13b240a27e862d3d4217c528e2e0c3
FROM ${PYTHON_BASE}

ARG MYSTACK_VERSION=0.1.4
ARG MYSTACK_CONFIG_SOURCE=config/mystack.yaml
LABEL org.opencontainers.image.title="Mystack AWS Proxy" \
      org.opencontainers.image.version="${MYSTACK_VERSION}" \
      org.opencontainers.image.source="https://github.com/leeyh0216/mystack"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MYSTACK_CONFIG_FILE=/etc/mystack/mystack.yaml

WORKDIR /opt/mystack
COPY requirements/proxy.txt /opt/requirements.txt
RUN python -m pip install --no-cache-dir --require-hashes -r /opt/requirements.txt
COPY shared /opt/src/shared
COPY proxy /opt/src/proxy
COPY ${MYSTACK_CONFIG_SOURCE} /etc/mystack/mystack.yaml
RUN python -m pip install --no-cache-dir --no-deps /opt/src/shared /opt/src/proxy \
    && rm -rf /opt/src /opt/requirements.txt

RUN addgroup --system mystack && adduser --system --ingroup mystack mystack
USER mystack

EXPOSE 8080
ENTRYPOINT ["mystack-proxy"]
CMD ["--config", "/etc/mystack/mystack.yaml"]
