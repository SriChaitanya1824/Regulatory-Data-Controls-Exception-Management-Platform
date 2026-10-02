import hashlib
import uuid
from pathlib import Path

from fastapi import UploadFile

from app.config import settings

ALLOWED = {"application/pdf", "image/png", "image/jpeg", "text/plain", "text/csv"}
MAX_BYTES = 10 * 1024 * 1024


class LocalEvidenceStorage:
    def save(self, upload: UploadFile) -> tuple[str, str]:
        if upload.content_type not in ALLOWED:
            raise ValueError("Unsupported evidence file type")
        data = upload.file.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES:
            raise ValueError("Evidence file exceeds 10 MB")
        suffix = Path(upload.filename or "evidence").suffix.lower()
        key = f"{uuid.uuid4().hex}{suffix}"
        root = Path(settings.evidence_dir).resolve()
        root.mkdir(parents=True, exist_ok=True)
        (root / key).write_bytes(data)
        return key, hashlib.sha256(data).hexdigest()


storage = LocalEvidenceStorage()
