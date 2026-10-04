FROM pytorch/pytorch:2.6.0-cuda12.4-cudnn9-devel

ENV DEBIAN_FRONTEND=noninteractive PYTHONUNBUFFERED=1 MAX_JOBS=2
RUN apt-get update && apt-get install -y --no-install-recommends git ffmpeg ninja-build && rm -rf /var/lib/apt/lists/*
WORKDIR /app
RUN git clone --depth 1 https://github.com/Wan-Video/Wan2.1.git /app/Wan2.1
RUN python -m pip install --no-cache-dir --upgrade pip setuptools wheel packaging ninja && \
    grep -v -E '^(torch|torchvision|flash_attn)([<>=].*)?$' /app/Wan2.1/requirements.txt > /tmp/wan-runtime.txt && \
    python -m pip install --no-cache-dir -r /tmp/wan-runtime.txt && \
    python -m pip install --no-cache-dir flash-attn --no-build-isolation && \
    python -m pip install --no-cache-dir "runpod>=1.7,<2" "fastapi>=0.115,<1" "uvicorn[standard]>=0.30,<1"
COPY handler.py /app/handler.py
ENV SARJAS_ROOT=/workspace/sarjas SARJAS_WAN_MODEL=/workspace/sarjas/models/Wan2.1-T2V-1.3B SARJAS_WAN_REPO=/app/Wan2.1 SARJAS_MODE=pod PORT=8000
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --retries=5 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health',timeout=3)"
CMD ["python","-u","/app/handler.py"]
