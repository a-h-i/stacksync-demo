
FROM python:3.12-slim AS base

# Install nsjail and minimal tools


RUN apt-get -y update && apt-get install -y \
    libc6 \
    libstdc++6 \
    libprotobuf32 \
    libnl-route-3-200

RUN apt-get install -y \
    autoconf \
    bison \
    flex \
    gcc \
    g++ \
    git \
    libprotobuf-dev \
    libnl-route-3-dev \
    libtool \
    make \
    pkg-config \
    protobuf-compiler

RUN git clone https://github.com/google/nsjail.git
WORKDIR /nsjail
RUN make clean && make
RUN cp nsjail /bin
WORKDIR /
RUN pip install poetry
RUN mkdir /app
WORKDIR /app
COPY src/* /app
COPY pyproject.toml poetry.lock README.md /app
RUN poetry install

RUN pip install numpy pandas



# Port for Cloud Run / local
ENV PORT=8080
EXPOSE 8080

# Gunicorn for production serving
CMD ["poetry", "run" ,"gunicorn","-b","0.0.0.0:8080","app:app","--workers","1","--threads","4","--timeout","0"]
