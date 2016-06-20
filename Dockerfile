FROM python:3.5
MAINTAINER 'Te-je Rodgers <tjd.rodgers@gmail.com>'

RUN mkdir -p /usr/src/glotpod
WORKDIR /usr/src/glotpod

COPY requirements.txt /usr/src/glotpod/requirements.txt
RUN pip install -r requirements.txt
COPY . /usr/src/glotpod
RUN pip install alembic -e /usr/src/glotpod

EXPOSE 80

CMD alembic upgrade head && python -m aiohttp.web -H 0.0.0.0 -P 80 glotpod.ident:init_app
