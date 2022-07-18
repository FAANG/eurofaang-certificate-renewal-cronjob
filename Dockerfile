FROM python:3.9.7
RUN python -m pip install --upgrade pip

WORKDIR /scripts
COPY ./update_eurofaang_certificate.py /scripts/
COPY ./config /scripts/
ADD requirements.txt ./
RUN pip install -r requirements.txt

ENV PYTHONBUFFERED=1



