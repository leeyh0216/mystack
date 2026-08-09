FROM python:3.11-slim-bookworm

WORKDIR /workspace
COPY requirements.txt .
RUN pip install --no-cache-dir --requirement requirements.txt
COPY verify.py .
CMD ["python", "verify.py"]
