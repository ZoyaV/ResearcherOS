FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY koi koi

ENV PYTHONPATH=/app
EXPOSE 8080

CMD ["uvicorn", "koi.paper.collaboration.signaling_service:app", "--host", "0.0.0.0", "--port", "8080"]
