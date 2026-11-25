FROM python:3.12-slim

WORKDIR /srv

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY nko ./nko

ENV DATA_DIR=/data \
    HOST=0.0.0.0 \
    PORT=8090 \
    PYTHONUNBUFFERED=1

EXPOSE 8090

CMD ["python", "-m", "nko"]
