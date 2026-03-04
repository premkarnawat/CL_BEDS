"""
CL-BEDS WebSocket Stream Routes
GET /ws/metrics  →  WebSocket endpoint for real-time biometric data
"""

import asyncio
import json
import logging
import time
import uuid
from typing import Optional

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from app.services.cmes_service import compute_cmes_index as compute_cmes
from app.services.fusion_service import fuse_modalities
from app.services.keystroke_service import compute_typing_irregularity as extract_keystroke_features
from app.services.mouse_service import compute_mouse_stiffness as extract_mouse_features
from app.services.rppg_service import compute_hrv_score as compute_hrv

router = APIRouter()
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Connection manager
# ---------------------------------------------------------------------------

class ConnectionManager:
    """Manages active WebSocket connections, keyed by user_id."""

    def __init__(self):
        self._connections: dict[str, list[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, user_id: str) -> None:
        await websocket.accept()
        self._connections.setdefault(user_id, []).append(websocket)
        logger.info("WS connected: user=%s  total=%d",
                    user_id, len(self._connections.get(user_id, [])))

    def disconnect(self, websocket: WebSocket, user_id: str) -> None:
        bucket = self._connections.get(user_id, [])
        if websocket in bucket:
            bucket.remove(websocket)
        logger.info("WS disconnected: user=%s", user_id)

    async def send_json(self, websocket: WebSocket, data: dict) -> None:
        try:
            await websocket.send_json(data)
        except Exception as exc:
            logger.debug("WS send error: %s", exc)


manager = ConnectionManager()

# ---------------------------------------------------------------------------
# WebSocket endpoint
# ---------------------------------------------------------------------------

@router.websocket("/metrics")
async def ws_metrics(
    websocket: WebSocket,
    token: Optional[str] = Query(default=None),
    session_id: Optional[str] = Query(default=None),
):
    """
    WebSocket endpoint for real-time cognitive load monitoring.

    Query params:
      token      : JWT access token (required)
      session_id : optional session UUID to associate data with

    Message format (client → server):
    {
      "type": "metrics_batch",
      "keystrokes": [...],
      "mouse_events": [...],
      "rppg": {...} | null,
      "text_snippet": "..." | null
    }

    Response (server → client):
    {
      "type": "risk_update",
      "session_id": "...",
      "timestamp": 1234567890.0,
      "keystroke_features": {...},
      "mouse_features": {...},
      "cmes": {...},
      "emotion": "...",
      "fusion": {...},
      "shap": {...}
    }
    """
    # --- Auth ---
    user_id = "anonymous"
    if token:
        try:
            from app.auth import decode_token
            payload = decode_token(token)
            user_id = payload["sub"]
        except Exception:
            await websocket.close(code=4001, reason="Invalid token")
            return

    sid = session_id or str(uuid.uuid4())
    await manager.connect(websocket, user_id)

    # --- Retrieve models from app state ---
    app = websocket.app
    burnout_model = getattr(app.state, "burnout_model", None)
    roberta_model = getattr(app.state, "roberta_model", None)

    if burnout_model is None:
        await websocket.close(code=1011, reason="Model not ready")
        manager.disconnect(websocket, user_id)
        return

    # --- Heartbeat task ---
    async def send_heartbeat():
        while True:
            await asyncio.sleep(30)
            try:
                await websocket.send_json({"type": "ping", "ts": time.time()})
            except Exception:
                break

    heartbeat_task = asyncio.create_task(send_heartbeat())

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                await manager.send_json(websocket, {"type": "error", "detail": "Invalid JSON"})
                continue

            msg_type = data.get("type", "metrics_batch")

            if msg_type == "pong":
                continue  # heartbeat acknowledgement

            if msg_type != "metrics_batch":
                await manager.send_json(websocket, {"type": "error", "detail": f"Unknown type: {msg_type}"})
                continue

            # --- Parse incoming payload ---
            from app.schemas.metrics import MetricsBatch, RPPGMetric
            try:
                batch = MetricsBatch(**data)
            except Exception as exc:
                await manager.send_json(websocket, {"type": "error", "detail": f"Validation error: {exc}"})
                continue

            # --- Feature extraction ---
            ks_features = extract_keystroke_features(batch.keystrokes)
            mouse_features = extract_mouse_features(batch.mouse_events)

            # HRV stress
            hrv_stress = 0.5
            if batch.rppg:
                hrv_result = compute_hrv([batch.rppg])
                if hrv_result:
                    hrv_stress = hrv_result.stress_index

            # CMES
            cmes_result = compute_cmes(ks_features, mouse_features, hrv_stress)

            # Emotion (NLP)
            emotion = "Neutral"
            sentiment_score = 0.0
            if batch.text_snippet and roberta_model:
                emotion, sentiment_score = roberta_model.predict(batch.text_snippet)
                # Map emotion to negative sentiment score
                _emotion_score_map = {
                    "Stress": 0.8,
                    "Fatigue": 0.7,
                    "Cognitive_Overload": 0.9,
                    "Neutral": 0.1,
                }
                sentiment_score = _emotion_score_map.get(emotion, 0.3)

            # --- Fusion ---
            live_response = await fuse_modalities(
                burnout_model=burnout_model,
                keystroke=ks_features,
                mouse=mouse_features,
                cmes=cmes_result,
                hrv_stress=hrv_stress,
                sentiment_score=sentiment_score,
                emotion=emotion,
                session_id=sid,
            )

            # --- Send response ---
            response_dict = live_response.model_dump()
            response_dict["type"] = "risk_update"
            await manager.send_json(websocket, response_dict)

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected for user %s", user_id)
    except Exception as exc:
        logger.exception("WebSocket error for user %s: %s", user_id, exc)
    finally:
        heartbeat_task.cancel()
        manager.disconnect(websocket, user_id)
