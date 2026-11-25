FROM python:3.12-slim

WORKDIR /srv

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY nko ./nko
COPY nko2 ./nko2

ENV DATA_DIR=/data \
    HOST=0.0.0.0 \
    PORT=8090 \
    PORT_V2=8091 \
    PYTHONUNBUFFERED=1

EXPOSE 8090 8091

CMD ["python", "-m", "nko"]
