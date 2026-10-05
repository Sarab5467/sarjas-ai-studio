FROM runpod/pytorch:1.0.2-cu1281-torch280-ubuntu2404

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    MAX_JOBS=2 \
    SARJAS_ROOT=/workspace/sarjas \
    SARJAS_WAN_MODEL=/workspace/sarjas/models/Wan2.1-T2V-1.3B \
    SARJAS_WAN_REPO=/app/Wan2.1 \
    HF_MODEL_REPO=SarabBagyana/sarjas-wan-runtime \
    SARJAS_MODE=pod \
    PORT=8000

RUN apt-get update && apt-get install -y --no-install-recommends git ffmpeg ninja-build ca-certificates && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app
RUN git clone --depth 1 https://github.com/Wan-Video/Wan2.1.git /app/Wan2.1

RUN python -m pip install --no-cache-dir --upgrade pip setuptools wheel packaging ninja && \
    grep -v -E '^(torch|torchvision|flash_attn)([<>=].*)?$' /app/Wan2.1/requirements.txt > /tmp/wan-runtime.txt && \
    python -m pip install --no-cache-dir -r /tmp/wan-runtime.txt && \
    python -m pip install --no-cache-dir "huggingface_hub>=0.27,<1" "fastapi>=0.115,<1" "uvicorn[standard]>=0.30,<1" && \
    python -m pip install --no-cache-dir flash-attn --no-build-isolation

COPY handler.py /app/handler.py
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=4 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health',timeout=3)"

CMD ["/app/entrypoint.sh"]
