FROM python:3.12-slim

WORKDIR /app
COPY app /app/app

ENV PYTHONUNBUFFERED=1

EXPOSE 40040 9100

CMD ["python", "-m", "app.main"]
