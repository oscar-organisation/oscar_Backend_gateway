ARG ROBOT_BASE_IMAGE
FROM ${ROBOT_BASE_IMAGE}

ARG OSCAR_EDGE_VERSION=dev
LABEL org.opencontainers.image.title="OSCAR Edge Runtime" \
      org.opencontainers.image.version="${OSCAR_EDGE_VERSION}"

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    OSCAR_EDGE_VERSION=${OSCAR_EDGE_VERSION}

WORKDIR /opt/oscar
COPY docker/requirements.txt /opt/oscar/requirements.txt
RUN python3 -m pip install --no-cache-dir -r /opt/oscar/requirements.txt

COPY runtime/ /opt/oscar/runtime/
COPY docker/entrypoint.sh /usr/local/bin/oscar-edge-entrypoint
RUN chmod 0755 /usr/local/bin/oscar-edge-entrypoint

HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=3 \
  CMD pgrep -f '[o]scar_robot_media.py' >/dev/null && pgrep -f '[c]ommand_agent.py' >/dev/null

ENTRYPOINT ["/usr/local/bin/oscar-edge-entrypoint"]
