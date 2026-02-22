FROM python:3.12-slim

WORKDIR /app

COPY client/requirements.txt /app/client/requirements.txt
RUN pip install --no-cache-dir -r /app/client/requirements.txt

COPY shared/ /app/shared/
COPY worker/ /app/worker/
COPY client/ /app/client/

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

CMD ["python", "-m", "client.main"]
