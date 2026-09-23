FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/

ENV ENVIRONMENT=production

CMD ["python", "src/run_pipeline.py"]
