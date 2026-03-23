FROM python:3.12-slim

WORKDIR /app

COPY services/runtime-api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/runtime-api/app/ ./app/

EXPOSE 8090

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8090"]
