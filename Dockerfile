FROM python:3.12-slim-bookworm AS builder
WORKDIR /build
COPY requirements.txt requirements-lock.txt ./
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

FROM python:3.12-slim-bookworm AS runtime
ARG SERVICE=ticket_api
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 SERVICE=${SERVICE}
RUN groupadd --gid 10001 app && useradd --uid 10001 --gid app --no-create-home app
COPY --from=builder /install /usr/local
WORKDIR /app
COPY services/common.py services/__init__.py ./services/
COPY services/${SERVICE}/ ./services/${SERVICE}/
USER 10001:10001
EXPOSE 8000
CMD ["sh", "-c", "exec uvicorn services.${SERVICE}.app:app --host 0.0.0.0 --port 8000 --no-access-log"]
