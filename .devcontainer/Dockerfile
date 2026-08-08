# syntax=docker/dockerfile:1.7
# Dev Container images: https://github.com/devcontainers/images
# MCR tag digest drift is checked against .devcontainer/images.json in CI.
ARG DEVCONTAINER_BASE=mcr.microsoft.com/devcontainers/python:1-3.11-bookworm
FROM ${DEVCONTAINER_BASE}

# The pinned upstream image currently configures Yarn's APT repository, while
# Mystack does not install Node or Yarn. Dev Container Features refresh every
# configured APT source, so an expired Yarn key would otherwise break unrelated
# Docker/AWS/GitHub CLI feature installation. Keep this compatibility shim next
# to the base image and remove it when the image lock advances.
# Upstream image source: https://github.com/devcontainers/images
RUN rm -f /etc/apt/sources.list.d/yarn.list

# Official uv Docker installation guidance:
# https://docs.astral.sh/uv/guides/integration/docker/#installing-uv
# Digest resolved from ghcr.io/astral-sh/uv:0.11.8.
COPY --from=ghcr.io/astral-sh/uv@sha256:3b7b60a81d3c57ef471703e5c83fd4aaa33abcd403596fb22ab07db85ae91347 /uv /uvx /usr/local/bin/
