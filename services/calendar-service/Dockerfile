FROM python:3.10-slim

WORKDIR /app

# Install shared library
COPY ./libs/shared-models /app/libs/shared-models
RUN pip install --no-cache-dir /app/libs/shared-models

COPY ./services/calendar-service/ /app/

RUN pip install --no-cache-dir -r requirements.txt

RUN useradd -r -s /bin/false appuser
USER appuser

EXPOSE 8050

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8050"]
