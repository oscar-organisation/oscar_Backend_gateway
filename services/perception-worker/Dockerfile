FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    OSCAR_MODEL_CACHE=/var/lib/oscar/models

RUN apt-get update \
    && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY perception_worker ./perception_worker
RUN useradd --system --uid 10001 --create-home oscar \
    && mkdir -p /var/lib/oscar/models \
    && chown -R oscar:oscar /var/lib/oscar

USER oscar
CMD ["python", "-m", "perception_worker.main"]
