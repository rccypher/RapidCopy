ARG STAGING_REGISTRY=localhost:5000
ARG STAGING_VERSION=latest

# Creates environment to run Seedsync python code
# Installs all python dependencies
FROM python:3.11-slim AS seedsync_run_python_env

# Install dependencies
# Handle both old (sources.list) and new (sources.list.d/*.sources) Debian formats
RUN if [ -f /etc/apt/sources.list ]; then \
        sed -i -e's/ main/ main contrib non-free/g' /etc/apt/sources.list; \
    elif [ -f /etc/apt/sources.list.d/debian.sources ]; then \
        sed -i 's/Components: main/Components: main contrib non-free non-free-firmware/g' /etc/apt/sources.list.d/debian.sources; \
    fi && \
    apt-get update && \
    apt-get install -y \
        gcc \
        libssl-dev \
        lftp \
        openssh-client \
        p7zip \
        p7zip-full \
        p7zip-rar \
        bzip2 \
        curl \
        libnss-wrapper \
        libxml2-dev libxslt-dev libffi-dev \
        zlib1g-dev \
    && apt-get clean
# Fix for patoolib (only needed in older Debian versions with p7zip)
# See: https://github.com/wummel/patool/issues/90
RUN if [ -f /usr/lib/p7zip/Codecs/Rar.so ]; then \
        ln -s /usr/lib/p7zip/Codecs/Rar.so /usr/lib/p7zip/Codecs/Rar29.so; \
    fi

# Install Poetry via pipx (isolated from project dependencies)
RUN curl -s https://bootstrap.pypa.io/get-pip.py -o get-pip.py && \
    python get-pip.py --force-reinstall && \
    rm get-pip.py
RUN pip3 install pipx && \
    pipx install poetry && \
    pipx ensurepath
ENV PATH="/root/.local/bin:${PATH}"
RUN poetry config virtualenvs.create false

ENV LC_ALL=C.UTF-8
ENV LANG=C.UTF-8

# Install Python dependencies
RUN mkdir -p /app
COPY src/python/pyproject.toml /app/python/
COPY src/python/poetry.lock /app/python/
RUN cd /app/python && poetry install --only main --no-root


# Creates environment for Python dev
FROM seedsync_run_python_env AS seedsync_run_python_devenv
RUN cd /app/python && poetry install --no-root


# Installs Seedsync python code
FROM seedsync_run_python_env AS seedsync_run_python
RUN mkdir -p /app
COPY src/python /app/python


# Full Seedsync docker image
FROM ${STAGING_REGISTRY}/seedsync/build/angular/export:${STAGING_VERSION} AS seedsync_build_angular_export
FROM ${STAGING_REGISTRY}/seedsync/build/scanfs/export:${STAGING_VERSION} AS seedsync_build_scanfs_export
FROM seedsync_run_python AS seedsync_run
COPY --from=seedsync_build_angular_export /html /app/html
COPY --from=seedsync_build_scanfs_export /scanfs /app/scanfs
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


# Create non-root user and directories under that user
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

# Must run app inside shell
# Otherwise the container crashes as soon as a child process exits
CMD [ \
    "python", \
    "/app/python/seedsync.py", \
    "-c", "/config", \
    "--html", "/app/html", \
    "--scanfs", "/app/scanfs" \
]

EXPOSE 8800
