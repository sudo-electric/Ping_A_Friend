FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 LC_ALL=C.UTF-8
WORKDIR /srv
RUN apt-get update && apt-get install -y --no-install-recommends iputils-ping \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 10001 paf && useradd --uid 10001 --gid paf --no-create-home paf \
    && mkdir /data && chown paf:paf /data
COPY requirements.lock .
RUN pip install --no-cache-dir -r requirements.lock
COPY app ./app
COPY config.example.json .
USER 10001:10001
EXPOSE 8000
CMD ["python", "-m", "app.launch", "--no-browser"]
