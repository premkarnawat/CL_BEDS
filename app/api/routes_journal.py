"""
CL-BEDS Journal Routes

POST   /journal
GET    /journal
GET    /journal/{entry_id}
DELETE /journal/{entry_id}
"""

import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import text

from app.dependencies import CurrentUser, DBSession, Pagination
from app.schemas.session import JournalEntryCreate, JournalEntryOut

router = APIRouter()
logger = logging.getLogger(__name__)


# -------------------------------------------------------------------
# Create Journal Entry
# -------------------------------------------------------------------

@router.post("", response_model=JournalEntryOut, status_code=status.HTTP_201_CREATED)
async def create_journal_entry(
    payload: JournalEntryCreate,
    current_user: CurrentUser,
    db: DBSession,
    request: Request,
):
    """Create a new journal entry."""

    entry_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    # NLP emotion detection (optional)
    detected_emotion = None

    try:
        roberta_model = getattr(request.app.state, "roberta_model", None)

        if roberta_model:
            emotion_label, _ = roberta_model.predict(payload.content)
            detected_emotion = emotion_label

    except Exception as e:
        logger.warning("Emotion detection failed: %s", e)

    db.execute(
        text("""
        INSERT INTO journal_entries
        (id, user_id, content, mood_score, tags, detected_emotion, created_at)
        VALUES
        (:id, :uid, :content, :mood, :tags, :emotion, :now)
        """),
        {
            "id": entry_id,
            "uid": current_user.sub,
            "content": payload.content,
            "mood": payload.mood_score,
            "tags": payload.tags,
            "emotion": detected_emotion,
            "now": now,
        },
    )

    return JournalEntryOut(
        id=entry_id,
        user_id=uuid.UUID(current_user.sub),
        content=payload.content,
        mood_score=payload.mood_score,
        tags=payload.tags,
        detected_emotion=detected_emotion,
        created_at=now,
    )


# -------------------------------------------------------------------
# List Journal Entries
# -------------------------------------------------------------------

@router.get("", response_model=list[JournalEntryOut])
async def list_journal_entries(
    current_user: CurrentUser,
    db: DBSession,
    pagination: Pagination,
):
    """List paginated journal entries."""

    result = db.execute(
        text("""
        SELECT id, user_id, content, mood_score, tags, detected_emotion, created_at
        FROM journal_entries
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
        JournalEntryOut(
            id=row.id,
            user_id=row.user_id,
            content=row.content,
            mood_score=row.mood_score,
            tags=row.tags,
            detected_emotion=row.detected_emotion,
            created_at=row.created_at,
        )
        for row in rows
    ]


# -------------------------------------------------------------------
# Get Single Journal Entry
# -------------------------------------------------------------------

@router.get("/{entry_id}", response_model=JournalEntryOut)
async def get_journal_entry(
    entry_id: uuid.UUID,
    current_user: CurrentUser,
    db: DBSession,
):
    """Fetch a specific journal entry."""

    result = db.execute(
        text("""
        SELECT id, user_id, content, mood_score, tags, detected_emotion, created_at
        FROM journal_entries
        WHERE id = :eid AND user_id = :uid
        """),
        {
            "eid": entry_id,
            "uid": current_user.sub,
        },
    )

    row = result.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Entry not found")

    return JournalEntryOut(
        id=row.id,
        user_id=row.user_id,
        content=row.content,
        mood_score=row.mood_score,
        tags=row.tags,
        detected_emotion=row.detected_emotion,
        created_at=row.created_at,
    )


# -------------------------------------------------------------------
# Delete Journal Entry
# -------------------------------------------------------------------

@router.delete("/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_journal_entry(
    entry_id: uuid.UUID,
    current_user: CurrentUser,
    db: DBSession,
):
    """Delete a journal entry."""

    result = db.execute(
        text("""
        DELETE FROM journal_entries
        WHERE id = :eid AND user_id = :uid
        RETURNING id
        """),
        {
            "eid": entry_id,
            "uid": current_user.sub,
        },
    )

    if not result.fetchone():
        raise HTTPException(status_code=404, detail="Entry not found")

    return None
