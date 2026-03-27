# Base Python image
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Install admin models library
COPY ./libs/admin-models /app/libs/admin-models
RUN pip install --no-cache-dir /app/libs/admin-models

# Copy application code and requirements
COPY ./services/admin-api/requirements.txt /app/
COPY ./services/admin-api/app /app/app

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Run as non-root
RUN useradd -r -s /bin/false appuser
USER appuser

EXPOSE 8001

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
