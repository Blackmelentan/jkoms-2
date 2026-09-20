"""
Local disk storage for uploaded files (avatars, proof-of-delivery photos,
signatures, customs documents). Every route that needs to save a file goes
through `save_upload` — if this ever needs to move to S3/MinIO/R2, that's a
one-file change here, not a hunt through every router.
"""

import os
import uuid
from pathlib import Path

from fastapi import UploadFile

from app.config import settings

UPLOAD_ROOT = Path(settings.upload_dir)
UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)


async def save_upload(file: UploadFile, subfolder: str) -> str:
    """Saves the file under uploads/<subfolder>/<uuid>-<original filename>
    and returns the public URL to store on the record (avatar_url,
    photo_url, file_url, etc.)."""
    folder = UPLOAD_ROOT / subfolder
    folder.mkdir(parents=True, exist_ok=True)

    safe_name = f"{uuid.uuid4().hex}-{os.path.basename(file.filename or 'upload')}"
    dest = folder / safe_name

    contents = await file.read()
    dest.write_bytes(contents)

    return f"{settings.public_upload_base_url}/{subfolder}/{safe_name}"
