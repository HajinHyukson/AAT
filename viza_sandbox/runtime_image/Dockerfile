FROM python:3.14-slim

RUN pip install --no-cache-dir pandas pyarrow numpy scipy statsmodels pydantic polars

COPY viza_sandbox/ /app/viza_sandbox/
COPY viza_sandbox/runtime_image/viza /app/viza

ENV PYTHONPATH=/app

RUN useradd --no-create-home --shell /usr/sbin/nologin sandbox
USER sandbox
