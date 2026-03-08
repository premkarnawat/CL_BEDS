"""
CL-BEDS AI Coach Chatbot Routes
POST /chat
GET  /chat/history
"""

import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks
from sqlalchemy import text

from app.dependencies import CurrentUser, DBSession, Pagination
from app.schemas.metrics import SHAPReport
from app.schemas.session import ChatMessageIn, ChatMessageOut, ChatResponse
from app.services.chatbot_service import get_coaching_response

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("", response_model=ChatResponse)
async def chat(payload: ChatMessageIn, current_user: CurrentUser, db: DBSession, background_tasks: BackgroundTasks):

    shap_report = None

    try:
        result = db.execute(
            text("""
                SELECT sr.risk_level, sr.confidence, sr.top_drivers, sr.session_id
                FROM shap_reports sr
                JOIN sessions s ON s.id = sr.session_id
                WHERE s.user_id = :uid
                ORDER BY sr.created_at DESC
                LIMIT 1
            """),
            {"uid": current_user.sub},
        )

        row = result.fetchone()

        if row:
            shap_report = SHAPReport(
                risk_level=row.risk_level,
                confidence=row.confidence,
                top_drivers=row.top_drivers,
                session_id=str(row.session_id),
            )

    except Exception as exc:
        logger.warning("SHAP fetch failed: %s", exc)

    history = []

    try:
        result = db.execute(
            text("""
                SELECT role, content, created_at
                FROM chat_logs
                WHERE user_id = :uid
                ORDER BY created_at DESC
                LIMIT 20
            """),
            {"uid": current_user.sub},
        )

        rows = result.fetchall()

        history = [
            ChatMessageOut(role=r.role, content=r.content, timestamp=r.created_at)
            for r in reversed(rows)
        ]

    except Exception as exc:
        logger.warning("History load failed: %s", exc)

    reply, tokens = await get_coaching_response(
        user_message=payload.content,
        history=history,
        shap_report=shap_report,
    )

    sid = payload.session_id or (str(shap_report.session_id) if shap_report else None)

    def save_messages():
        try:
            now = datetime.now(tz=timezone.utc)

            db.execute(
                text("""
                    INSERT INTO chat_logs (id, user_id, session_id, role, content, created_at)
                    VALUES
                    (:uid1, :user_id, :sid, 'user', :user_msg, :now),
                    (:uid2, :user_id, :sid, 'assistant', :assistant_msg, :now)
                """),
                {
                    "uid1": str(uuid.uuid4()),
                    "uid2": str(uuid.uuid4()),
                    "user_id": current_user.sub,
                    "sid": sid,
                    "user_msg": payload.content,
                    "assistant_msg": reply,
                    "now": now,
                },
            )

        except Exception as exc:
            logger.error("Chat save failed: %s", exc)

    background_tasks.add_task(save_messages)

    return ChatResponse(reply=reply, session_id=sid, tokens_used=tokens)


@router.get("/history", response_model=list[ChatMessageOut])
async def get_chat_history(current_user: CurrentUser, db: DBSession, pagination: Pagination):

    result = db.execute(
        text("""
            SELECT role, content, created_at
            FROM chat_logs
            WHERE user_id = :uid
            ORDER BY created_at DESC
            LIMIT :limit OFFSET :offset
        """),
        {
            "uid": current_user.sub,
            "limit": pagination.page_size,
            "offset": pagination.offset,
        },
    )

    rows = result.fetchall()

    return [
        ChatMessageOut(role=r.role, content=r.content, timestamp=r.created_at)
        for r in reversed(rows)
    ]
