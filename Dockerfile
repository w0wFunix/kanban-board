# Контейнер собирается из АРТЕФАКТА (папка build/ = распакованный kanban-*.tar.gz),
# а не из исходников: build/app, build/static, build/requirements.txt
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PORT=8000 STATIC_DIR=/app/static
WORKDIR /app

COPY build/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY build/ .
RUN useradd --create-home app && chown -R app /app
USER app

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD python -c "import os,urllib.request;urllib.request.urlopen('http://localhost:'+os.environ['PORT']+'/health')" || exit 1

CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT}
