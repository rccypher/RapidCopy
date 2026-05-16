# RapidCopy Dockerfile
# Uses pre-built Angular frontend from host, builds Python backend in container

FROM ubuntu:22.04 AS seedsync_run

ENV DEBIAN_FRONTEND=noninteractive

# Install Python 3 and system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        python3 \
        python3-pip \
        python3-setuptools \
        lftp \
        openssh-client \
        p7zip \
        p7zip-full \
        bzip2 \
        curl \
        libnss-wrapper \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Install Python dependencies directly via pip
RUN pip3 install --no-cache-dir \
    --trusted-host pypi.org --trusted-host files.pythonhosted.org \
    bottle \
    paste \
    patool \
    pexpect \
    pytz \
    requests \
    tblib \
    timeout-decorator

# python -> python3 symlink for compatibility
RUN ln -sf /usr/bin/python3 /usr/bin/python

ENV LC_ALL=C.UTF-8
ENV LANG=C.UTF-8

# Copy Python source code
RUN mkdir -p /app
COPY src/python /app/python

# Copy pre-built Angular frontend
COPY build/html /app/html

# Copy self-contained scanfs script
COPY src/python/scanfs_standalone.py /app/scanfs
RUN chmod +x /app/scanfs

# Copy config setup script
COPY src/docker/build/docker-image/setup_default_config.sh /scripts/

# Disable the known hosts prompt
RUN mkdir -p /root/.ssh && printf "StrictHostKeyChecking no\nUserKnownHostsFile /dev/null\n" > /root/.ssh/config

# SSH as any user fix
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
    "python3", \
    "/app/python/seedsync.py", \
    "-c", "/config", \
    "--html", "/app/html", \
    "--scanfs", "/app/scanfs" \
]

EXPOSE 8800
