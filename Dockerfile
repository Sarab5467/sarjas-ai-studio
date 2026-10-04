FROM nvidia/cuda:12.4.1-cudnn-runtime-ubuntu22.04
ENV DEBIAN_FRONTEND=noninteractive PYTHONUNBUFFERED=1
RUN apt-get update && apt-get install -y --no-install-recommends python3 python3-pip python3-dev ffmpeg git build-essential && rm -rf /var/lib/apt/lists/*
WORKDIR /app
RUN git clone --depth 1 https://github.com/Wan-Video/Wan2.1.git /app/Wan2.1
RUN pip3 install --no-cache-dir --upgrade pip setuptools wheel packaging && pip3 install --no-cache-dir torch torchvision && pip3 install --no-cache-dir -r /app/Wan2.1/requirements.txt && pip3 install --no-cache-dir "runpod>=1.7,<2" "fastapi>=0.115,<1" "uvicorn[standard]>=0.30,<1"
COPY handler.py /app/handler.py
ENV SARJAS_ROOT=/workspace/sarjas SARJAS_WAN_MODEL=/workspace/sarjas/models/Wan2.1-T2V-1.3B SARJAS_WAN_REPO=/app/Wan2.1 SARJAS_MODE=pod PORT=8000
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --retries=5 CMD python3 -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health',timeout=3)"
CMD ["python3","-u","/app/handler.py"]
