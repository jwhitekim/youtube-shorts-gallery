import asyncio
import os
from datetime import datetime, timezone

import httpx
from fastapi import HTTPException
from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from app.db.supabase import (
    get_existing_video_ids,
    get_last_sync_time,
    get_shorts_count,
    get_user_by_id,
    update_last_sync,
    update_user_tokens,
    upsert_shorts,
)

_SHORTS_CONCURRENCY = 10


async def _check_is_short(client: httpx.AsyncClient, video_id: str) -> bool:
    try:
        resp = await client.head(
            f"https://www.youtube.com/shorts/{video_id}",
            follow_redirects=False,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        return resp.status_code == 200
    except Exception:
        return False


async def _bulk_check_shorts(video_ids: list[str]) -> dict[str, bool]:
    sem = asyncio.Semaphore(_SHORTS_CONCURRENCY)

    async def check(client: httpx.AsyncClient, vid: str) -> tuple[str, bool]:
        async with sem:
            return vid, await _check_is_short(client, vid)

    async with httpx.AsyncClient(timeout=10) as client:
        results = await asyncio.gather(*[check(client, vid) for vid in video_ids])

    return dict(results)


async def _get_credentials(user: dict) -> Credentials:
    creds = Credentials(
        token=user["access_token"],
        refresh_token=user["refresh_token"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ["GOOGLE_CLIENT_ID"],
        client_secret=os.environ["GOOGLE_CLIENT_SECRET"],
    )

    expires_at = user.get("token_expires_at")
    if expires_at:
        if isinstance(expires_at, str):
            expiry = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
        else:
            expiry = expires_at
        # google-auth compares expiry with utcnow() (naive), so strip tzinfo
        if expiry.tzinfo is not None:
            expiry = expiry.replace(tzinfo=None)
        creds.expiry = expiry

    if creds.expired and creds.refresh_token:
        creds.refresh(GoogleRequest())
        await update_user_tokens(
            user["id"],
            access_token=creds.token,
            token_expires_at=creds.expiry.isoformat() if creds.expiry else None,
        )

    return creds


async def sync_liked_shorts(user_id: str) -> dict:
    user = await get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # 5-minute sync cooldown
    last_sync = await get_last_sync_time(user_id)
    if last_sync:
        last_sync_dt = datetime.fromisoformat(last_sync.replace("Z", "+00:00"))
        if last_sync_dt.tzinfo is None:
            last_sync_dt = last_sync_dt.replace(tzinfo=timezone.utc)
        elapsed = (datetime.now(timezone.utc) - last_sync_dt).total_seconds()
        if elapsed < 300:
            total = await get_shorts_count(user_id)
            return {"added": 0, "total": total, "cached": True}

    creds = await _get_credentials(user)
    youtube = build("youtube", "v3", credentials=creds, cache_discovery=False)

    # Step 1: collect up to 200 liked video IDs + liked timestamps
    video_liked: list[tuple[str, str]] = []
    next_page_token = None

    while len(video_liked) < 2000:
        resp = youtube.playlistItems().list(
            playlistId="LL",
            part="snippet,contentDetails",
            maxResults=50,
            pageToken=next_page_token,
        ).execute()

        for item in resp.get("items", []):
            video_id = item["contentDetails"]["videoId"]
            liked_at = item["snippet"].get("publishedAt", "")
            video_liked.append((video_id, liked_at))

        next_page_token = resp.get("nextPageToken")
        if not next_page_token:
            break

    # Step 2: batch-fetch titles
    liked_map = {vid: ts for vid, ts in video_liked}
    all_ids = list(liked_map.keys())
    shorts: list[dict] = []

    for i in range(0, len(all_ids), 50):
        batch = all_ids[i : i + 50]
        resp = youtube.videos().list(
            id=",".join(batch),
            part="snippet",
        ).execute()

        for item in resp.get("items", []):
            vid_id = item["id"]
            title = item["snippet"].get("title", "")
            shorts.append({
                "video_id": vid_id,
                "title": title,
                "liked_at": liked_map.get(vid_id, ""),
            })

    # HTTP-check is_short only for videos not yet in DB
    existing_ids = await get_existing_video_ids(user_id)
    new_ids = [v["video_id"] for v in shorts if v["video_id"] not in existing_ids]
    if new_ids:
        is_short_map = await _bulk_check_shorts(new_ids)
        for v in shorts:
            if v["video_id"] in is_short_map:
                v["is_short"] = is_short_map[v["video_id"]]

    added = await upsert_shorts(user_id, shorts, existing_ids)
    await update_last_sync(user_id)
    total = await get_shorts_count(user_id)

    return {"added": added, "total": total}
