FROM nvidia/cuda:12.4.1-cudnn-runtime-ubuntu22.04
ENV DEBIAN_FRONTEND=noninteractive PYTHONUNBUFFERED=1
RUN apt-get update && apt-get install -y --no-install-recommends python3 python3-pip python3-dev ffmpeg git build-essential && rm -rf /var/lib/apt/lists/*
WORKDIR /app
RUN git clone --depth 1 https://github.com/Wan-Video/Wan2.1.git /app/Wan2.1
RUN pip3 install --no-cache-dir -r /app/Wan2.1/requirements.txt && pip3 install --no-cache-dir "runpod>=1.7,<2"
COPY handler.py /app/handler.py
ENV SARJAS_ROOT=/runpod-volume/sarjas
ENV SARJAS_WAN_MODEL=/runpod-volume/sarjas/models/Wan2.1-T2V-1.3B
ENV SARJAS_WAN_REPO=/app/Wan2.1
CMD ["python3", "-u", "/app/handler.py"]
