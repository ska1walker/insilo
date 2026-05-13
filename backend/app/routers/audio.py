"""Audio streaming endpoint for the local storage backend.

When `STORAGE_BACKEND=local`, the meetings router returns relative URLs of
the form `/api/v1/audio/<org_id>/<filename>` instead of S3 presigned URLs.
The browser fetches them through the Next.js proxy, which forwards the
X-Bfl-User header that Olares' frontend Envoy injects. Starlette's
FileResponse handles HTTP Range natively, so the <audio> player can seek.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from app.auth import CurrentUser, get_current_user
from app.config import settings
from app.storage import _LocalBackend, backend

router = APIRouter(prefix="/api/v1", tags=["audio"])


_AUDIO_MIME = {
    "webm": "audio/webm",
    "m4a": "audio/mp4",
    "ogg": "audio/ogg",
    "wav": "audio/wav",
}


@router.get("/audio/{org_id}/{filename}")
async def get_audio(
    org_id: UUID,
    filename: str,
    user: CurrentUser = Depends(get_current_user),
) -> FileResponse:
    if settings.storage_backend != "local":
        raise HTTPException(404, "audio streaming only available for local backend")

    if user.org_id != org_id:
        raise HTTPException(403, "forbidden")

    # Path-traversal defense: filenames are flat UUID-based names like
    # "<meeting_id>.webm". No slashes, no parent refs.
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(400, "invalid filename")

    local = backend
    if not isinstance(local, _LocalBackend):
        raise HTTPException(500, "storage misconfigured")

    key = f"{org_id}/{filename}"
    path = local.local_path(key)
    if not path.exists() or not path.is_file():
        raise HTTPException(404, "audio not found")

    ext = filename.rsplit(".", 1)[-1].lower()
    media_type = _AUDIO_MIME.get(ext, "application/octet-stream")
    return FileResponse(path=path, media_type=media_type, filename=filename)
