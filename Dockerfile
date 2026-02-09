# All-in-one SeedSync Dockerfile
# Builds Angular frontend, scanfs script, and Python backend in one image
# No staging registry required

# Stage 1: Build Angular frontend
FROM node:12.16 AS angular_build
COPY src/angular/package*.json /app/
WORKDIR /app
RUN npm install
COPY src/angular /app
RUN mkdir -p /build/html && node_modules/@angular/cli/bin/ng build -prod --output-path /build/html/

# Stage 2: Build Python environment and final image
FROM python:3.8-slim AS seedsync_run

# Enable non-free repos (handle both old sources.list and new .sources format)
RUN if [ -f /etc/apt/sources.list ]; then \
        sed -i -e's/ main/ main contrib non-free/g' /etc/apt/sources.list; \
    elif [ -d /etc/apt/sources.list.d ]; then \
        for f in /etc/apt/sources.list.d/*.sources; do \
            [ -f "$f" ] && sed -i 's/^Components: main$/Components: main contrib non-free/' "$f"; \
        done; \
    fi

# Install dependencies
RUN apt-get update && \
    apt-get install -y \
        gcc \
        libssl-dev \
        lftp \
        openssh-client \
        p7zip \
        p7zip-full \
        bzip2 \
        curl \
        libnss-wrapper \
        libxml2-dev libxslt-dev libffi-dev \
    && apt-get clean

# Install Poetry
RUN curl -s https://bootstrap.pypa.io/pip/3.8/get-pip.py -o get-pip.py && \
    python get-pip.py --force-reinstall && \
    rm get-pip.py
RUN pip3 install poetry
RUN poetry config virtualenvs.create false

ENV LC_ALL=C.UTF-8
ENV LANG=C.UTF-8

# Install Python dependencies
RUN mkdir -p /app
COPY src/python/pyproject.toml /app/python/
COPY src/python/poetry.lock /app/python/
RUN cd /app/python && poetry install --no-dev

# Copy Python source code
COPY src/python /app/python

# Copy Angular build output
COPY --from=angular_build /build/html /app/html

# Create scanfs wrapper script (uses scan_fs.py directly instead of PyInstaller binary)
RUN echo '#!/bin/sh' > /app/scanfs && \
    echo 'exec python /app/python/scan_fs.py "$@"' >> /app/scanfs && \
    chmod +x /app/scanfs

# Copy config setup script
COPY src/docker/build/docker-image/setup_default_config.sh /scripts/

# Disable the known hosts prompt
RUN mkdir -p /root/.ssh && echo "StrictHostKeyChecking no\nUserKnownHostsFile /dev/null" > /root/.ssh/config

# SSH as any user fix
# https://stackoverflow.com/a/57531352
COPY src/docker/build/docker-image/run_as_user /usr/local/bin/
RUN chmod a+x /usr/local/bin/run_as_user
COPY src/docker/build/docker-image/ssh /usr/local/sbin
RUN chmod a+x /usr/local/sbin/ssh
COPY src/docker/build/docker-image/scp /usr/local/sbin
RUN chmod a+x /usr/local/sbin/scp

# Create non-root user and directories
RUN groupadd -g 1000 seedsync && \
    useradd -r -u 1000 -g seedsync seedsync
RUN mkdir /config && \
    mkdir /downloads && \
    chown seedsync:seedsync /config && \
    chown seedsync:seedsync /downloads

# Switch to non-root user
USER seedsync

# First time config setup and replacement
RUN /scripts/setup_default_config.sh

CMD [ \
    "python", \
    "/app/python/seedsync.py", \
    "-c", "/config", \
    "--html", "/app/html", \
    "--scanfs", "/app/scanfs" \
]

EXPOSE 8800
