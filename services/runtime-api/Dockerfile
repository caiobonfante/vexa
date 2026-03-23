FROM python:3.12-slim

WORKDIR /app

# Shared models (DB, auth, token_scope)
COPY libs/shared-models /app/libs/shared-models
RUN pip install --no-cache-dir /app/libs/shared-models

COPY services/runtime-api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/runtime-api/app/ ./app/

EXPOSE 8090

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8090"]
