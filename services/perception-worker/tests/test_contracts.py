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


def test_lurl_locale_prime_sur_celle_annoncee_par_lapi():
    """Le worker tournant a cote du SFU doit joindre le media en direct.

    Par le nom public, depuis le meme hote, la signalisation aboutit — le
    participant apparait actif cote serveur — mais l'abonnement aux pistes
    n'arrive jamais. Le jeton reste emis par l'API ; seule l'URL est locale.
    """
    import inspect

    from perception_worker import worker

    source = inspect.getsource(worker.PerceptionWorker.run)
    assert "self.config.livekit_url or session.livekit_url" in source


def test_la_room_est_creee_dans_la_boucle():
    """Regression : une room construite hors boucle ne recoit aucun evenement.

    `rtc.Room` capture `asyncio.get_event_loop()` a sa creation. Construire le
    worker avant `asyncio.run` l'attache a une boucle qui ne tournera jamais :
    la connexion reussit, le participant apparait actif cote serveur, et aucune
    piste n'est jamais analysee.
    """
    import ast
    import inspect

    from perception_worker import main as module

    arbre = ast.parse(inspect.getsource(module))
    fonction = next(n for n in arbre.body
                    if isinstance(n, ast.FunctionDef) and n.name == "main")
    appels = [n for n in ast.walk(fonction) if isinstance(n, ast.Call)]
    constructions = [n for n in appels
                     if isinstance(n.func, ast.Name) and n.func.id == "PerceptionWorker"]
    assert not constructions, (
        "PerceptionWorker doit etre instancie dans une coroutine, pas dans main()"
    )
