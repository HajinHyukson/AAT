FROM python:3.14.10-slim

RUN pip install --no-cache-dir \
    pandas==3.1.1 \
    pyarrow==26.0.1 \
    numpy==2.5.5 \
    scipy==1.18.1 \
    statsmodels==0.15.0 \
    pydantic==2.14.3 \
    polars==2.1.0

COPY viza_sandbox/ /app/viza_sandbox/
COPY viza_sandbox/runtime_image/viza /app/viza

ENV PYTHONPATH=/app

RUN useradd --no-create-home --shell /usr/sbin/nologin sandbox
USER sandbox
