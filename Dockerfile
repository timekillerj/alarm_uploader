FROM python:3.6-slim

ENV PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

RUN apt-get update && apt-get install -y curl unzip man-db

COPY ./requirements.txt /app/

RUN pip install -r /app/requirements.txt
RUN apt-get remove -y gcc && apt-get autoremove -y

RUN curl https://rclone.org/install.sh | bash
COPY . /app/

CMD ["python", "/app/alarm_uploader.py"]
