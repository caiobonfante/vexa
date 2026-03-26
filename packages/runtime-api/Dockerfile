FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY pyproject.toml .
RUN pip install --no-cache-dir .

# Copy application
COPY runtime_api/ runtime_api/
COPY profiles.example.yaml profiles.yaml

EXPOSE 8090

CMD ["uvicorn", "runtime_api.main:app", "--host", "0.0.0.0", "--port", "8090"]
