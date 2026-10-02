import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.models import AuditLog


def audit(db: Session, actor_id: int | None, action: str, entity_type: str, entity_id: int,
          before: dict[str, Any] | None = None, after: dict[str, Any] | None = None) -> None:
    db.add(AuditLog(actor_id=actor_id, action=action, entity_type=entity_type, entity_id=entity_id,
                    before_value=before, after_value=after, request_id=str(uuid.uuid4())))

