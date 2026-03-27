FROM python:3.10-slim

WORKDIR /app

# Install admin models (User, APIToken)
COPY ./libs/admin-models /app/libs/admin-models
RUN pip install --no-cache-dir /app/libs/admin-models

# Install meeting-api models (CalendarEvent, database)
COPY ./packages/meeting-api /app/packages/meeting-api
RUN pip install --no-cache-dir /app/packages/meeting-api

COPY ./services/calendar-service/ /app/

RUN pip install --no-cache-dir -r requirements.txt

RUN useradd -r -s /bin/false appuser
USER appuser

EXPOSE 8050

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8050"]
