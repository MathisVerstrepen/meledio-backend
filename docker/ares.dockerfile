# docker build -t dune_ares:latest -f ares.dockerfile ../

FROM python:3.9

# # Adding trusting keys to apt for repositories
# RUN wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add -

# # Adding Google Chrome to the repositories
# RUN sh -c 'echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list'

# # Updating apt to see and install Google Chrome
RUN apt-get -y update

# # Magic happens
# RUN apt-get install -y google-chrome-stable

# # Installing Unzip
# RUN apt-get install -yqq unzip

# # Download the Chrome Driver
# RUN wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add -
# RUN sh -c 'echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list'
# RUN apt-get -y update
# RUN apt-get install -y google-chrome-stable

# # install chromedriver
# RUN apt-get install -yqq unzip
# RUN wget -O /tmp/chromedriver.zip http://chromedriver.storage.googleapis.com/`curl -sS chromedriver.storage.googleapis.com/LATEST_RELEASE`/chromedriver_linux64.zip
# RUN unzip /tmp/chromedriver.zip chromedriver -d /usr/local/bin/

# # Set display port as an environment variable
# ENV DISPLAY=:99

RUN apt-get install -y ffmpeg

WORKDIR /ares

COPY ./docker/conf/ares-requirements.txt /ares/requirements.txt

RUN pip install --no-cache-dir --upgrade -r /ares/requirements.txt

COPY ./ares /ares

CMD ["uvicorn", "app.main:ares", "--proxy-headers", "--host", "0.0.0.0", "--port", "5100", "--reload"]
