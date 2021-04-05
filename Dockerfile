FROM python:3.8-buster

ENV QUEUE_USE_ENV=1

COPY queuebot.py requirements-prod.txt /app/
WORKDIR /app/
RUN pip install --no-cache-dir -r requirements-prod.txt

ENTRYPOINT [ "python", "queuebot.py" ]