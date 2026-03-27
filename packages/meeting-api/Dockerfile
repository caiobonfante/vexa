FROM python:3.11-slim

WORKDIR /app

# Install system deps
RUN apt-get update && apt-get install -y --no-install-recommends gcc && rm -rf /var/lib/apt/lists/*

# Install Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy admin models (auth, token_scope)
COPY libs/admin-models /admin-models
RUN pip install --no-cache-dir /admin-models

# Copy app code
COPY packages/meeting-api .

CMD ["uvicorn", "meeting_api.main:app", "--host", "0.0.0.0", "--port", "8080"]
