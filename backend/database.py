import os
from functools import lru_cache
from supabase import create_client, Client
from datetime import datetime, timezone

_sync_times: dict[str, str] = {}


@lru_cache(maxsize=1)
def get_supabase() -> Client:
    return create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])


async def upsert_user(
    google_id: str,
    email: str,
    access_token: str,
    refresh_token: str | None,
    token_expires_at: str | None,
) -> dict:
    supabase = get_supabase()
    data: dict = {
        "google_id": google_id,
        "email": email,
        "access_token": access_token,
        "token_expires_at": token_expires_at,
    }
    if refresh_token:
        data["refresh_token"] = refresh_token
    result = supabase.table("users").upsert(data, on_conflict="google_id").execute()
    return result.data[0]


async def get_user_by_id(user_id: str) -> dict | None:
    supabase = get_supabase()
    result = supabase.table("users").select("*").eq("id", user_id).maybe_single().execute()
    return result.data


async def update_user_tokens(user_id: str, access_token: str, token_expires_at: str | None):
    supabase = get_supabase()
    supabase.table("users").update({
        "access_token": access_token,
        "token_expires_at": token_expires_at,
    }).eq("id", user_id).execute()


async def upsert_shorts(user_id: str, shorts: list[dict]) -> int:
    if not shorts:
        return 0
    supabase = get_supabase()

    existing = supabase.table("shorts").select("video_id").eq("user_id", user_id).execute()
    existing_ids = {r["video_id"] for r in (existing.data or [])}

    new_shorts = [s for s in shorts if s["video_id"] not in existing_ids]
    if not new_shorts:
        return 0

    data = [
        {
            "user_id": user_id,
            "video_id": s["video_id"],
            "title": s["title"],
            "is_short": True,
            "liked_at": s.get("liked_at"),
        }
        for s in new_shorts
    ]
    supabase.table("shorts").insert(data).execute()
    return len(new_shorts)


async def get_shorts(user_id: str) -> list[dict]:
    supabase = get_supabase()
    result = (
        supabase.table("shorts")
        .select("*")
        .eq("user_id", user_id)
        .eq("is_short", True)
        .order("display_order", desc=False, nullsfirst=False)
        .order("liked_at", desc=True)
        .execute()
    )
    return result.data or []


async def get_shorts_count(user_id: str) -> int:
    supabase = get_supabase()
    result = (
        supabase.table("shorts")
        .select("id", count="exact")
        .eq("user_id", user_id)
        .execute()
    )
    return result.count or 0


async def delete_short(user_id: str, video_id: str):
    supabase = get_supabase()
    supabase.table("shorts").delete().eq("user_id", user_id).eq("video_id", video_id).execute()


async def reorder_shorts(user_id: str, video_ids: list[str]):
    supabase = get_supabase()
    for i, video_id in enumerate(video_ids):
        supabase.table("shorts").update({"display_order": i}).eq("user_id", user_id).eq("video_id", video_id).execute()


async def get_last_sync_time(user_id: str) -> str | None:
    return _sync_times.get(user_id)


async def update_last_sync(user_id: str):
    _sync_times[user_id] = datetime.now(timezone.utc).isoformat()
