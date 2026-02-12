# Creates environment to build python binaries
FROM python:3.11-slim AS rapidcopy_build_pyinstaller_env

# Install build dependencies
RUN apt-get update && apt-get install -y \
    binutils \
    curl \
    zlib1g-dev \
    gcc \
    python3-dev \
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


# Builds rapidcopy with pyinstaller
# Output is in /build/dist/rapidcopy/
FROM rapidcopy_build_pyinstaller_env AS rapidcopy_build_pyinstaller
COPY src/python /python
COPY src/pyinstaller_hooks /pyinstaller_hooks
RUN mkdir -p /build
RUN pyinstaller /python/rapidcopy.py \
    -y \
    -p /python \
    --distpath /build/dist \
    --workpath /build/work \
    --specpath /build \
    --additional-hooks-dir /pyinstaller_hooks/ \
    --hidden-import="pkg_resources.py2_warn" \
    --name rapidcopy


# Builds scanfs with pyinstaller
# Output is in /build/dist/
FROM rapidcopy_build_pyinstaller_env AS rapidcopy_build_scanfs
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
# Note: Using Node 18 for Angular 18 compatibility
FROM node:18-slim AS rapidcopy_build_angular_env
COPY src/angular/package*.json /app/
WORKDIR /app
RUN npm install

# Builds angular app into html
# Output is in /build/dist/
FROM rapidcopy_build_angular_env AS rapidcopy_build_angular
# Copy source files but preserve node_modules from previous stage
COPY src/angular/src /app/src
COPY src/angular/public /app/public
COPY src/angular/angular.json /app/
COPY src/angular/tsconfig*.json /app/
WORKDIR /app
RUN npx ng build --configuration production --output-path /build/dist/


# Creates environment to build deb packages
# Using Ubuntu 22.04 LTS for deb packaging
FROM ubuntu:22.04 AS rapidcopy_build_deb_env
RUN apt-get update && apt-get install -y \
    build-essential \
    debhelper \
    devscripts \
    && rm -rf /var/lib/apt/lists/*


# Builds debian package
# Output is in /build/dist/
FROM rapidcopy_build_deb_env AS rapidcopy_build_deb
RUN mkdir -p /build/work
COPY src/debian /build/work/debian
COPY --from=rapidcopy_build_pyinstaller /build/dist/rapidcopy /build/work/rapidcopy
COPY --from=rapidcopy_build_scanfs /build/dist/scanfs /build/work/rapidcopy/
COPY --from=rapidcopy_build_angular /build/dist /build/work/rapidcopy/html
WORKDIR /build/work
RUN dpkg-buildpackage -B -uc -us
RUN ls /build/*.deb && echo "----" && ls /build/work


# Exports deb package to host
FROM scratch AS rapidcopy_build_deb_export
COPY --from=rapidcopy_build_deb /build/*.deb .

# Exports scanfs to host
FROM scratch AS rapidcopy_build_scanfs_export
COPY --from=rapidcopy_build_scanfs /build/dist/scanfs .

# Exports html to host
FROM scratch AS rapidcopy_build_angular_export
COPY --from=rapidcopy_build_angular /build/dist ./html
