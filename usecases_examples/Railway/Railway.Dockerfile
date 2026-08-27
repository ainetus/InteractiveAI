FROM python:3.10-slim

WORKDIR /app

# System deps for flatland/numpy/PIL
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ libffi-dev && \
    rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all Railway source files
COPY . .

# Persistent volumes: logs, maps, sessions
VOLUME ["/app/experiment_logs", "/app/maps"]

EXPOSE 5001

ENV FLASK_ENV=production
ENV PYTHONUNBUFFERED=1

CMD ["python", "app.py"]
