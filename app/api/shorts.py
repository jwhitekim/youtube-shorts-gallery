from fastapi import APIRouter, HTTPException, Request

from core.database import delete_short, get_shorts, reorder_shorts
from core.youtube import sync_liked_shorts

router = APIRouter(prefix="/shorts")


def _require_user(request: Request) -> str:
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user_id


@router.get("/sync")
async def sync_shorts(request: Request):
    user_id = _require_user(request)
    return await sync_liked_shorts(user_id)


@router.get("")
async def list_shorts(request: Request):
    user_id = _require_user(request)
    return await get_shorts(user_id)


@router.delete("/{video_id}")
async def delete_short_item(video_id: str, request: Request):
    user_id = _require_user(request)
    await delete_short(user_id, video_id)
    return {"status": "ok"}


@router.patch("/reorder")
async def reorder_short_items(request: Request):
    user_id = _require_user(request)
    body = await request.json()
    video_ids: list[str] = body.get("video_ids", [])
    await reorder_shorts(user_id, video_ids)
    return {"status": "ok"}
