FROM python:3.12-slim

WORKDIR /app

# Copy source and install
COPY pyproject.toml README.md ./
COPY runtime_api/ runtime_api/
COPY profiles.example.yaml profiles.yaml
RUN pip install --no-cache-dir .

EXPOSE 8090

CMD ["uvicorn", "runtime_api.main:app", "--host", "0.0.0.0", "--port", "8090"]
