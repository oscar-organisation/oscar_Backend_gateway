from pathlib import Path

from .base import ModelAdapter
from ..schemas import ModelManifest


def create_adapter(manifest: ModelManifest, artifact: Path) -> ModelAdapter:
    if manifest.runtime in {"ultralytics", "pytorch"}:
        from .yolo import UltralyticsAdapter

        return UltralyticsAdapter(manifest, artifact)
    raise ValueError(
        f"Runtime {manifest.runtime!r} enregistré mais non exécutable par cette image worker. "
        "Installez son adaptateur avant activation."
    )
