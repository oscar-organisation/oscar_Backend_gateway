import pytest
from pydantic import ValidationError

from perception_worker.schemas import Detection, OverlayPacket, WorkerSession


def test_overlay_packet_uses_normalized_coordinates():
    packet = OverlayPacket(
        robot_id="robot-1", room="oscar-robot-1", frame_timestamp_us=123,
        frame_width=640, frame_height=480, model_id="model-1", model_name="Retail",
        model_version="1.0.0", task="product_detection",
        detections=[Detection(
            detection_id="d1", label="produit", class_id=0, confidence=0.91,
            x=0.1, y=0.2, width=0.3, height=0.4,
        )],
    )
    assert b"oscar.vision.overlay.v1" in packet.wire_bytes()


def test_detection_rejects_out_of_frame_box():
    with pytest.raises(ValidationError):
        Detection(
            detection_id="d1", label="bad", class_id=0, confidence=0.9,
            x=1.2, y=0.2, width=0.3, height=0.4,
        )

    with pytest.raises(ValidationError):
        Detection(
            detection_id="d2", label="wide", class_id=0, confidence=0.9,
            x=0.8, y=0.2, width=0.3, height=0.4,
        )


def test_worker_session_contract():
    session = WorkerSession(
        livekit_url="wss://stream.example.test",
        room="oscar-robot-1",
        identity="vision-robot-1",
        token="signed-token",
        expires_in_seconds=86400,
    )
    assert session.room == "oscar-robot-1"


def test_lossy_overlay_packet_stays_under_mtu():
    detections = [Detection(
        detection_id=f"detection-{index}", label=f"produit-{index}", class_id=index,
        confidence=0.5 + index / 100, x=0.1, y=0.1, width=0.2, height=0.2,
    ) for index in range(20)]
    packet = OverlayPacket(
        robot_id="robot-1", room="oscar-robot-1", frame_timestamp_us=123,
        frame_width=640, frame_height=480, model_id="model-1", model_name="Retail",
        model_version="1.0.0", task="product_detection", detections=detections,
    )
    payload = packet.lossy_wire_bytes()
    assert len(payload) <= 1200
    assert b'"detections_total":20' in payload
