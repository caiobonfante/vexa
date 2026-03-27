FROM python:3.12-slim

WORKDIR /app

# Docker CLI binary (static, for container management via subprocess)
RUN apt-get update && apt-get install -y --no-install-recommends curl && \
    curl -fsSL https://download.docker.com/linux/static/stable/x86_64/docker-27.5.1.tgz | \
    tar xz --strip-components=1 -C /usr/local/bin docker/docker && \
    apt-get purge -y curl && apt-get autoremove -y && \
    rm -rf /var/lib/apt/lists/*

# Runtime API (scheduler library)
COPY packages/runtime-api /app/packages/runtime-api
RUN pip install --no-cache-dir /app/packages/runtime-api

# Admin models (security headers)
COPY libs/admin-models /app/libs/admin-models
RUN pip install --no-cache-dir /app/libs/admin-models

COPY services/agent-api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/agent-api/app/ ./app/

EXPOSE 8100

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8100"]
