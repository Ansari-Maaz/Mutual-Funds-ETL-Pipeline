FROM python:3.10-slim
WORKDIR /app
COPY requirements.txt pyproject.toml ./
COPY app ./app
COPY config ./config
COPY migrations ./migrations
COPY alembic.ini ./alembic.ini
COPY reports/source_catalogue.json ./reports/source_catalogue.json
RUN pip install --no-cache-dir .
CMD ["python", "-m", "app.cli", "--help"]
