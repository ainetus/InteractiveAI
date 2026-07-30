# syntax=docker/dockerfile:1

FROM python:3.9-slim-bullseye

RUN mkdir /code
WORKDIR /code

# --no-install-recommends + cleaning the apt lists keeps the image small.
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg libsm6 libxext6 \
  && rm -rf /var/lib/apt/lists/*

# copy requirements and install BEFORE copying the source, so the (slow)
# dependency layer stays cached and is only rebuilt when requirements change,
# not on every code edit. --no-cache-dir avoids bundling pip's cache in the image.
COPY requirements-app.txt /code/requirements-app.txt
RUN pip3 install --no-cache-dir -r requirements-app.txt

COPY . /code/

CMD ["python3", "PowerGrid_poc_simulator_app.py"]
