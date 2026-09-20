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
COPY docker/healthcheck-container.sh /usr/local/bin/oscar-edge-healthcheck
RUN chmod 0755 /usr/local/bin/oscar-edge-entrypoint /usr/local/bin/oscar-edge-healthcheck

# La sante suit ce que le bundle a active, agents comme mise en route.
HEALTHCHECK --interval=15s --timeout=10s --start-period=90s --retries=3 \
  CMD /usr/local/bin/oscar-edge-healthcheck

ENTRYPOINT ["/usr/local/bin/oscar-edge-entrypoint"]
