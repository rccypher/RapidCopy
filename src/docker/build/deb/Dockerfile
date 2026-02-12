# Creates environment to build python binaries
FROM python:3.11-slim as seedsync_build_pyinstaller_env

# Install build dependencies
RUN apt-get update && apt-get install -y \
    binutils \
    curl \
    zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry via pipx for isolation
RUN pip install --no-cache-dir pipx && \
    pipx install poetry && \
    pipx ensurepath
ENV PATH="/root/.local/bin:$PATH"

# Configure Poetry
RUN poetry config virtualenvs.create false

# Copy and install dependencies
COPY src/python/pyproject.toml /app/python/
COPY src/python/poetry.lock /app/python/
WORKDIR /app/python
ENV LC_ALL=C.UTF-8
ENV LANG=C.UTF-8
RUN poetry install --only main --no-root && \
    poetry install --only dev --no-root


# Builds seedsync with pyinstaller
# Output is in /build/dist/seedsync/
FROM seedsync_build_pyinstaller_env as seedsync_build_pyinstaller
COPY src/python /python
COPY src/pyinstaller_hooks /pyinstaller_hooks
RUN mkdir -p /build
RUN pyinstaller /python/seedsync.py \
    -y \
    -p /python \
    --distpath /build/dist \
    --workpath /build/work \
    --specpath /build \
    --additional-hooks-dir /pyinstaller_hooks/ \
    --hidden-import="pkg_resources.py2_warn" \
    --name seedsync


# Builds scanfs with pyinstaller
# Output is in /build/dist/
FROM seedsync_build_pyinstaller_env as seedsync_build_scanfs
COPY src/python /python
RUN mkdir -p /build
RUN	pyinstaller /python/scan_fs.py \
    -y \
    --onefile \
    -p /python \
    --distpath /build/dist \
    --workpath /build/work \
    --specpath /build \
    --name scanfs


# Creates environment for angular
# Note: Using Node 12 as Angular 4 requires Node <= 12
FROM node:12.22-slim as seedsync_build_angular_env
COPY src/angular/package*.json /app/
WORKDIR /app
RUN npm install

# Builds angular app into html
# Output is in /build/dist/
FROM seedsync_build_angular_env as seedsync_build_angular
COPY src/angular /app
WORKDIR /app
RUN node_modules/@angular/cli/bin/ng build -prod --output-path /build/dist/


# Creates environment to build deb packages
# Using Ubuntu 22.04 LTS for deb packaging
FROM ubuntu:22.04 as seedsync_build_deb_env
RUN apt-get update && apt-get install -y \
    build-essential \
    debhelper \
    devscripts \
    && rm -rf /var/lib/apt/lists/*


# Builds debian package
# Output is in /build/dist/
FROM seedsync_build_deb_env as seedsync_build_deb
RUN mkdir -p /build/work
COPY src/debian /build/work/debian
COPY --from=seedsync_build_pyinstaller /build/dist/seedsync /build/work/seedsync
COPY --from=seedsync_build_scanfs /build/dist/scanfs /build/work/seedsync/
COPY --from=seedsync_build_angular /build/dist /build/work/seedsync/html
WORKDIR /build/work
RUN dpkg-buildpackage -B -uc -us
RUN ls /build/*.deb && echo "----" && ls /build/work


# Exports deb package to host
FROM scratch AS seedsync_build_deb_export
COPY --from=seedsync_build_deb /build/*.deb .

# Exports scanfs to host
FROM scratch AS seedsync_build_scanfs_export
COPY --from=seedsync_build_scanfs /build/dist/scanfs .

# Exports html to host
FROM scratch AS seedsync_build_angular_export
COPY --from=seedsync_build_angular /build/dist ./html
