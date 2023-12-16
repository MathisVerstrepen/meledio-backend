# docker build -t dune_triton:latest -f triton.dockerfile ../

FROM python:3.10

WORKDIR /triton

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1\
    PYTHONIOENCODING=utf-8

RUN apt-get -y update && apt-get -y install ffmpeg && apt-get clean

COPY ./docker/conf/triton-requirements.txt /triton/requirements.txt
RUN pip install --no-cache-dir --upgrade -r /triton/requirements.txt

COPY ./triton /triton

CMD ["uvicorn", "app.main:triton", "--proxy-headers", "--host", "0.0.0.0", "--port", "5110", "--reload"]
