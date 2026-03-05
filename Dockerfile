FROM python:3.12-alpine

# Dependencias runtime
RUN apk add --no-cache \
    ffmpeg \
    opus \
    libsodium \
    nodejs

RUN apk add --no-cache --virtual .build-deps \
    gcc \
    musl-dev \
    libffi-dev \
    libsodium-dev \
    opus-dev

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

RUN apk del .build-deps

COPY . .
CMD ["python", "bot.py"]
