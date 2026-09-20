from typing import Literal

from fastapi import APIRouter, UploadFile, File

from app.deps import CurrentUser
from app.storage import save_upload

router = APIRouter(prefix="/uploads", tags=["uploads"])

Subfolder = Literal["avatars", "proof-of-delivery", "documents"]


@router.post("/{subfolder}")
async def upload_file(subfolder: Subfolder, user: CurrentUser, file: UploadFile = File(...)):
    """Returns {"url": "..."} - the caller (frontend) then PATCHes that URL
    onto whatever record it belongs to (profile.avatar_url, a journey
    event's photo_url, a documents row, etc.). Kept generic rather than
    one endpoint per use case since the save logic is identical."""
    url = await save_upload(file, subfolder)
    return {"url": url}
