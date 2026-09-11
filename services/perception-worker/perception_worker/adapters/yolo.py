import uuid
from pathlib import Path

import numpy as np

from .base import ModelAdapter
from ..schemas import Detection, ModelManifest


class UltralyticsAdapter(ModelAdapter):
    def __init__(self, manifest: ModelManifest, artifact: Path):
        super().__init__(manifest, artifact)
        from ultralytics import YOLO

        self.model = YOLO(str(artifact), task="detect")

    def infer(self, rgb_frame: np.ndarray) -> list[Detection]:
        height = int(self.manifest.input.get("height", 640))
        width = int(self.manifest.input.get("width", 640))
        result = self.model.predict(
            source=rgb_frame,
            imgsz=(height, width),
            conf=self.manifest.confidence,
            iou=self.manifest.iou_threshold,
            verbose=False,
        )[0]
        if result.boxes is None:
            return []

        boxes = result.boxes.xyxyn.cpu().numpy()
        confidences = result.boxes.conf.cpu().numpy()
        classes = result.boxes.cls.cpu().numpy().astype(int)
        names = result.names or {}
        detections = []
        for (x1, y1, x2, y2), confidence, class_id in zip(boxes, confidences, classes):
            left = float(max(0.0, min(1.0, x1)))
            top = float(max(0.0, min(1.0, y1)))
            right = float(max(0.0, min(1.0, x2)))
            bottom = float(max(0.0, min(1.0, y2)))
            if right <= left or bottom <= top:
                continue
            detections.append(Detection(
                detection_id=uuid.uuid4().hex,
                label=str(names.get(int(class_id), class_id)),
                class_id=int(class_id),
                confidence=float(confidence),
                x=left,
                y=top,
                width=right - left,
                height=bottom - top,
            ))
        return detections
