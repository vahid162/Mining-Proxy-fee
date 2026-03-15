FROM python:3.12-slim

WORKDIR /app

# Create non-root runtime user for better container hardening.
RUN useradd --create-home --uid 10001 appuser

COPY app /app/app

ENV PYTHONUNBUFFERED=1

# Compose controls published ports; expose documents internal listeners.
EXPOSE 40040 9100

USER appuser

CMD ["python", "-m", "app.main"]
