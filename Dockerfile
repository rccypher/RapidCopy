# RapidCopy - Single-stage local build Dockerfile
# Usage: docker build -t rapidcopy:latest .

# ============================================
# Stage 1: Build Angular frontend
# ============================================
FROM node:18-slim AS angular-builder

WORKDIR /app
COPY src/angular/package*.json ./
RUN npm install

COPY src/angular/src ./src
COPY src/angular/public ./public
COPY src/angular/angular.json ./
COPY src/angular/tsconfig*.json ./
RUN npx ng build --configuration production --output-path /build/html

# ============================================
# Stage 2: Build scanfs binary
# ============================================
FROM python:3.11-slim-bullseye AS scanfs-builder

RUN apt-get update && apt-get install -y \
    binutils \
    zlib1g-dev \
    gcc \
    build-essential \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir pipx && \
    pipx install poetry && \
    pipx ensurepath
ENV PATH="/root/.local/bin:$PATH"
RUN poetry config virtualenvs.create false

COPY src/python/pyproject.toml src/python/poetry.lock /app/
WORKDIR /app
ENV LC_ALL=C.UTF-8
ENV LANG=C.UTF-8
RUN poetry install --only main --no-root && \
    poetry install --only dev --no-root

COPY src/python /python
RUN pyinstaller /python/scan_fs.py \
    -y \
    --onefile \
    -p /python \
    --distpath /build \
    --workpath /tmp/work \
    --specpath /tmp \
    --name scanfs

# ============================================
# Stage 3: Runtime image
# ============================================
FROM python:3.11-slim AS runtime

# Install runtime dependencies
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
        bzip2 \
        curl \
        libnss-wrapper \
        libxml2-dev libxslt-dev libffi-dev \
        zlib1g-dev \
        # Network mount support (NFS/SMB/CIFS)
        nfs-common \
        cifs-utils \
        keyutils \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN pip install --no-cache-dir pipx && \
    pipx install poetry && \
    pipx ensurepath
ENV PATH="/root/.local/bin:${PATH}"
RUN poetry config virtualenvs.create false

ENV LC_ALL=C.UTF-8
ENV LANG=C.UTF-8

# Install Python dependencies
COPY src/python/pyproject.toml src/python/poetry.lock /app/python/
RUN cd /app/python && poetry install --only main --no-root

# Copy Python source
COPY src/python /app/python

# Copy built artifacts from previous stages
COPY --from=angular-builder /build/html/browser /app/html
COPY --from=scanfs-builder /build/scanfs /app/scanfs

# Copy helper scripts
COPY src/docker/build/docker-image/setup_default_config.sh /scripts/
COPY src/docker/build/docker-image/run_as_user /usr/local/bin/
COPY src/docker/build/docker-image/ssh /usr/local/sbin/
COPY src/docker/build/docker-image/scp /usr/local/sbin/

RUN chmod a+x /usr/local/bin/run_as_user && \
    chmod a+x /usr/local/sbin/ssh && \
    chmod a+x /usr/local/sbin/scp && \
    chmod a+rx /scripts/setup_default_config.sh

# Disable SSH known hosts prompt
RUN mkdir -p /root/.ssh && \
    echo "StrictHostKeyChecking no\nUserKnownHostsFile /dev/null" > /root/.ssh/config

# Create non-root user
RUN groupadd -g 1000 rapidcopy && \
    useradd -r -u 1000 -g rapidcopy rapidcopy && \
    mkdir /config && \
    mkdir /downloads && \
    mkdir /mounts && \
    mkdir /logs && \
    chown rapidcopy:rapidcopy /config && \
    chown rapidcopy:rapidcopy /downloads && \
    chown rapidcopy:rapidcopy /mounts && \
    chown rapidcopy:rapidcopy /logs

USER rapidcopy

# Setup default config
RUN /scripts/setup_default_config.sh

CMD [ \
    "python", \
    "/app/python/rapidcopy.py", \
    "-c", "/config", \
    "--html", "/app/html", \
    "--scanfs", "/app/scanfs", \
    "--logdir", "/logs" \
]

EXPOSE 8800
