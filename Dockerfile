FROM python:latest

WORKDIR /usr/src/app

COPY . .
RUN pip install --no-cache-dir -r requirements.txt

RUN mkdir -p /config/savedplots

VOLUME /config

ENTRYPOINT [ "python", "./smerac.py" ]
