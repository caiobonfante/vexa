FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends gcc && rm -rf /var/lib/apt/lists/*

COPY packages/agent-runtime/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY packages/agent-runtime .

CMD ["uvicorn", "agent_runtime.main:app", "--host", "0.0.0.0", "--port", "8100"]
