FROM python:3.5
MAINTAINER 'Te-je Rodgers <tjd.rodgers@gmail.com>'

RUN mkdir -p /usr/src/glotpod
WORKDIR /usr/src/glotpod

COPY requirements.txt /usr/src/glotpod/requirements.txt
RUN pip install gunicorn alembic -r requirements.txt
COPY . /usr/src/glotpod
RUN pip install -e /usr/src/glotpod

EXPOSE 80

CMD ["bin/sh", "-c", "alembic upgrade head && exec gunicorn glotpod.ident:app -b 0.0.0.0:80 --worker-class aiohttp.worker.GunicornWebWorker"]
