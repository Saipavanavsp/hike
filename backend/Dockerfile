# ---- builder: install deps into a venv and fetch the ONNX model ----
FROM python:3.11-slim AS builder

ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /build
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY scripts/download_model.py scripts/download_model.py
RUN python scripts/download_model.py /models/all-MiniLM-L6-v2

# ---- runtime ----
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    MODEL_DIR=/models/all-MiniLM-L6-v2 \
    EMBEDDING_BACKEND=onnx \
    STORAGE_DIR=/data/storage

RUN useradd --create-home --uid 1000 hike && mkdir -p /data/storage && chown -R hike /data

COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /models /models

WORKDIR /app
COPY --chown=hike . .
RUN chmod +x scripts/start.sh

USER hike
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --start-period=40s --retries=5 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/health').status==200 else 1)"

CMD ["./scripts/start.sh"]
