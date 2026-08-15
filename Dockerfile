# Use the official Python image for ARM64
FROM python:3.12-slim

# The tagged version to install from PyPI, e.g. "1.47.0".
ARG VERSION

# Set the working directory in the container
WORKDIR /app

# Install build dependencies, needed if a dependency has no prebuilt wheel
# for this platform.
RUN apt-get update && \
    apt-get install -y gcc python3-dev && \
    rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Install the already-published, already-built release from PyPI. Its wheel
# already contains the compiled webui JS bundle and translation files, so no
# source checkout or Node.js toolchain is needed here.
RUN uv pip install --system geo-activity-playground==${VERSION}

RUN mkdir /data

EXPOSE 5000

CMD ["python", "-m", "geo_activity_playground", "--basedir", "/data", "serve", "--host", "0.0.0.0"]
