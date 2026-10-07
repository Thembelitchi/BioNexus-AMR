FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml README.md ./
COPY bionexus ./bionexus
RUN pip install --no-cache-dir .

RUN useradd --create-home bionexus
USER bionexus
EXPOSE 8000
CMD ["uvicorn", "--factory", "bionexus.api:create_app", "--host", "0.0.0.0", "--port", "8000"]
