FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1

WORKDIR /app

# Runtime deps only: the dev lock minus dev/test tools and the local-only Postgres bundle.
COPY requirements-dev.lock ./
RUN grep -viE '^(pgserver|pytest|ruff|iniconfig|pluggy)' requirements-dev.lock > /tmp/req.txt \
    && pip install -r /tmp/req.txt

COPY . .
RUN pip install --no-deps .

# Chromium for scrapers is large; build with --build-arg WITH_BROWSER=1 to include it.
ARG WITH_BROWSER=0
RUN if [ "$WITH_BROWSER" = "1" ]; then playwright install --with-deps chromium; fi

RUN useradd --create-home --uid 10001 app && chown -R app /app
USER app

EXPOSE 8000
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log", \
     "--proxy-headers", "--forwarded-allow-ips", "*"]
