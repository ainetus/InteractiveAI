# syntax=docker/dockerfile:1
# The Railway simulator as a service (app.py): idle until the Railway page's start dialog starts a
# session, then it plays the run list and sends its events and contexts to the platform.
FROM python:3.11-slim

WORKDIR /code
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py ./
COPY sim/ sim/
COPY integration/ integration/
COPY experiment_scenarios/ experiment_scenarios/
COPY maps/ maps/

EXPOSE 5124
CMD ["python", "app.py"]
