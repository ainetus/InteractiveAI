# syntax=docker/dockerfile:1

FROM python:3.9-slim-bullseye
EXPOSE 5000

RUN mkdir /code
COPY . /code/
WORKDIR /code

RUN pip3 install -r requirements-app.txt

CMD ["python3", "PowerGrid_poc_simulator_app.py"]