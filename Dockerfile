FROM python:alpine3.19

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apk --no-cache update && \
    apk --no-cache add bash ffmpeg

RUN addgroup nonroot && \
    adduser -s bash -D -G nonroot nonroot

RUN mkdir --mode u+rw /var/log/app && \
    chown nonroot:nonroot /var/log/app

USER nonroot
WORKDIR /app

COPY requirements.txt requirements.txt
RUN pip --no-cache-dir install -U pip && \
    pip --no-cache-dir install -r requirements.txt && \
    rm requirements.txt

COPY --chown=nonroot . .
RUN chmod u+x start

CMD ["./start"]
