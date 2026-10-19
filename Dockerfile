FROM python:3.10-slim
WORKDIR /app
COPY requirements.txt pyproject.toml ./
COPY app ./app
COPY config ./config
RUN pip install --no-cache-dir .
CMD ["python", "-m", "app.cli", "--help"]
