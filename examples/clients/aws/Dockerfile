FROM python:3.11-slim-bookworm

WORKDIR /workspace
RUN apt-get update \
    && apt-get install --yes --no-install-recommends awscli \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir --requirement requirements.txt
COPY verify.py lab.sh .
RUN chmod 0755 lab.sh
CMD ["./lab.sh"]
