# Image OSCAR Edge : le runtime OSCAR seul, sans la pile du constructeur.
#
# Les pilotes du chassis tournent dans l'image du constructeur, deja presente
# sur le robot, dans un conteneur a part (service « chassis » de compose.yaml).
# Les deux se parlent par ROS 2. Cette image ne depend donc que de la
# distribution ROS, et sert toutes les familles de chassis qui la partagent.
ARG ROS_DISTRO=humble

# --- Interfaces du chassis --------------------------------------------------
# Compilees a part : la chaine de compilation ne passe pas dans l'image finale.
FROM ros:${ROS_DISTRO}-ros-base AS interfaces
RUN apt-get update \
 && apt-get install -y --no-install-recommends build-essential cmake \
 && rm -rf /var/lib/apt/lists/*
COPY interfaces/ /src/interfaces/
RUN . /opt/ros/${ROS_DISTRO}/setup.sh \
 && colcon build --base-paths /src/interfaces --build-base /tmp/build \
      --install-base /opt/oscar/interfaces --merge-install

# --- Runtime ----------------------------------------------------------------
FROM ros:${ROS_DISTRO}-ros-base

RUN apt-get update \
 && apt-get install -y --no-install-recommends python3-pip \
 && rm -rf /var/lib/apt/lists/*

# Les dependances avant le code et avant la version : une nouvelle version ne
# change ni l'une ni l'autre, et retrouve cette couche en cache.
WORKDIR /opt/oscar
COPY docker/requirements.txt /opt/oscar/requirements.txt
RUN python3 -m pip install --no-cache-dir -r /opt/oscar/requirements.txt

COPY --from=interfaces /opt/oscar/interfaces /opt/oscar/interfaces
COPY runtime/ /opt/oscar/runtime/
COPY docker/entrypoint.sh /usr/local/bin/oscar-edge-entrypoint
COPY docker/healthcheck-container.sh /usr/local/bin/oscar-edge-healthcheck
RUN chmod 0755 /usr/local/bin/oscar-edge-entrypoint /usr/local/bin/oscar-edge-healthcheck

# En dernier : seule couche qui change d'une version a l'autre sans code modifie.
ARG OSCAR_EDGE_VERSION=dev
LABEL org.opencontainers.image.title="OSCAR Edge Runtime" \
      org.opencontainers.image.version="${OSCAR_EDGE_VERSION}"
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    OSCAR_INTERFACES_SETUP=/opt/oscar/interfaces/setup.bash \
    OSCAR_EDGE_VERSION=${OSCAR_EDGE_VERSION}

# La sante ne juge plus la mise en route du chassis, qui vit dans son propre
# conteneur : la periode de grace couvre la connexion a la salle et les
# premieres images.
HEALTHCHECK --interval=15s --timeout=10s --start-period=90s --retries=3 \
  CMD /usr/local/bin/oscar-edge-healthcheck

ENTRYPOINT ["/usr/local/bin/oscar-edge-entrypoint"]
