
FROM python:3.12-slim AS builder

# Install nsjail and minimal tools


RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y \
    build-essential git pkg-config \
    flex bison \
    clang \
    libprotobuf-dev protobuf-compiler \
    libnl-route-3-dev \
    libcap-dev \
    libssl-dev \
 && rm -rf /var/lib/apt/lists/*

RUN git clone --depth 1 --recursive https://github.com/google/nsjail.git /tmp/nsjail \
 && make -C /tmp/nsjail clean \
 && make -C /tmp/nsjail -j"$(nproc)" \
 && mv /tmp/nsjail/nsjail /usr/local/bin/nsjail \
 && rm -rf /tmp/nsjail



FROM python:3.11-slim AS runner

RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y \
    libnl-route-3-200 \
    protobuf-compiler \
    && rm -rf /var/lib/apt/list


COPY --from=builder /usr/local/bin/nsjail /usr/local/bin/nsjail

RUN pip install flask numpy pandas poetry
RUN mkdir /app
WORKDIR /app
COPY src/* /app
COPY pyproject.toml poetry.lock README.md /app
RUN poetry install




# Port for Cloud Run / local
ENV PORT=8080
EXPOSE 8080

# Gunicorn for production serving
CMD ["poetry", "run" ,"gunicorn","-b","0.0.0.0:8080","app:app","--workers","1","--threads","4","--timeout","0"]
