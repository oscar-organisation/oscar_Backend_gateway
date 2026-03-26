# ==============================================================================
# Dockerfile - Simulateur Média (Robot Publisher Python)
# ==============================================================================
# Ce conteneur empaquète le script Python (implémentation OpenCV native) 
# responsable de la publication vidéo. 

FROM python:3.11-slim

# On coupe les dialogues systèmes d'Ubuntu/Debian (installations automatiques)
ENV DEBIAN_FRONTEND=noninteractive

# Installation des bibliothèques fondamentales matérielles pour le noyau OpenCV C++.
# libGL1 et libglib gèrent la liaison directe avec les bus graphiques ou caméras virtuelles.
RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Isolation des layers : on télécharge les dépendances lourdes (Numpy, OpenCV, LiveKit) en premier.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Ajout du script logiciel métier
COPY simulate.py .

# Paramètre '-u' : Force Python à cracher ses print "en direct" (unbuffered) pour lire confortablement `docker logs`
CMD ["python", "-u", "simulate.py"]
