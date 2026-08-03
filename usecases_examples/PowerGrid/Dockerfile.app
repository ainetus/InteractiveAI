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
# not on every code edit. The pip cache mount keeps downloaded wheels out of
# the final image while still persisting them across builds (so a retry
# after a network blip, or a real requirements change, doesn't have to
# re-download unchanged packages).
COPY requirements-app.txt /code/requirements-app.txt
RUN --mount=type=cache,target=/root/.cache/pip pip3 install -r requirements-app.txt

COPY . /code/

CMD ["python3", "PowerGrid_poc_simulator_app.py"]
