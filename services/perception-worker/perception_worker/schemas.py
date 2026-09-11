from __future__ import annotations

from pydantic import BaseModel, Field, field_validator, model_validator


class ModelManifest(BaseModel):
    id: str
    name: str
    version: str
    task: str
    runtime: str
    sha256: str
    artifact_name: str
    artifact_path: str
    input: dict = Field(default_factory=dict)
    output: dict = Field(default_factory=dict)
    labels: list[str] = Field(default_factory=list)
    inference_fps: int = Field(default=5, ge=1, le=30)
    confidence: float = Field(default=0.25, ge=0, le=1)
    iou_threshold: float = Field(default=0.45, ge=0, le=1)
    overlay_enabled: bool = True
    incident_enabled: bool = False
    config: dict = Field(default_factory=dict)


class RuntimeManifest(BaseModel):
    schema_version: str
    robot_id: str
    room: str
    overlay_topic: str = "oscar.vision.overlay"
    models: list[ModelManifest] = Field(default_factory=list)


class WorkerSession(BaseModel):
    livekit_url: str
    room: str
    identity: str
    token: str
    expires_in_seconds: int


class Detection(BaseModel):
    detection_id: str
    label: str
    class_id: int
    confidence: float = Field(ge=0, le=1)
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    width: float = Field(ge=0, le=1)
    height: float = Field(ge=0, le=1)

    @field_validator("width", "height")
    @classmethod
    def non_zero_extent(cls, value: float) -> float:
        if value <= 0:
            raise ValueError("une boîte doit avoir une taille positive")
        return value

    @model_validator(mode="after")
    def contained_in_frame(self):
        if self.x + self.width > 1.000001 or self.y + self.height > 1.000001:
            raise ValueError("une boîte doit rester dans les coordonnées normalisées de l'image")
        return self


class OverlayPacket(BaseModel):
    schema_version: str = Field(default="oscar.vision.overlay.v1", alias="schema")
    robot_id: str
    room: str
    frame_timestamp_us: int
    frame_width: int
    frame_height: int
    model_id: str
    model_name: str
    model_version: str
    task: str
    detections: list[Detection]
    detections_total: int | None = None

    def wire_bytes(self) -> bytes:
        return self.model_dump_json(by_alias=True, exclude_none=True).encode("utf-8")

    def lossy_wire_bytes(self, max_bytes: int = 1200) -> bytes:
        """Fit the freshest/highest-confidence boxes inside one network MTU."""
        packet = self.model_copy(deep=True)
        packet.detections.sort(key=lambda item: item.confidence, reverse=True)
        packet.detections_total = len(packet.detections)
        payload = packet.wire_bytes()
        while len(payload) > max_bytes and packet.detections:
            packet.detections.pop()
            payload = packet.wire_bytes()
        if len(payload) > max_bytes:
            raise ValueError("les métadonnées de l'overlay dépassent la taille d'un paquet lossy")
        return payload
