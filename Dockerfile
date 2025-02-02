FROM python:3.9-alpine as base
FROM base as builder

RUN mkdir /install
WORKDIR /install

COPY requirements.txt /
RUN pip install --no-warn-script-location --prefix=/install -r /requirements.txt

FROM base
STOPSIGNAL SIGINT
COPY --from=builder /install /usr/local
COPY amcrest2mqtt /amcrest2mqtt
WORKDIR /

CMD [ "python", "-u", "-m", "amcrest2mqtt" ]
