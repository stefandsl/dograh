# Telegram bot container — see ADR-100 (aiogram framework) and ADR-101
# (audio bridge: voice-note round-trip + WebApp link, no aiortc).
#
# debian-slim, NOT alpine — opus/srtp/ffmpeg wheels resolve cleanly on
# manylinux against glibc; alpine forces source rebuilds (see ADR-101).
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Voice-note round-trip needs ffmpeg for Opus/OGG transcoding.
# curl is for the healthcheck.
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
        ffmpeg \
        libopus0 \
        libopusfile0 \
        curl \
        ca-certificates \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install -r requirements.txt

COPY bot /app/bot

# Healthcheck endpoint bound on 8080; nothing else listens here.
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --retries=3 --start-period=20s \
    CMD curl -fsS http://localhost:8080/healthz || exit 1

CMD ["python", "-m", "bot.main"]
