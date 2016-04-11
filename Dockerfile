FROM python:3.5
ADD . /glotpod/ident
RUN pip install /glotpod/ident
CMD ["python", "-m", "glotpod.ident"]
