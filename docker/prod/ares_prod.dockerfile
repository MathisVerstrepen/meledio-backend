# sudo docker build -t dune_ares:latest -f ares_dev.dockerfile ../

FROM python:3.11

WORKDIR /ares

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1\
    PYTHONIOENCODING=utf-8

RUN apt-get -y update && apt-get -y install ffmpeg && apt-get clean

COPY ./docker/conf/ares-requirements.txt /ares/requirements.txt
RUN pip install --no-cache-dir --upgrade -r /ares/requirements.txt

COPY ./ares /ares

CMD ["uvicorn", "app.main:ares", "--proxy-headers", "--host", "0.0.0.0", "--port", "5100"]