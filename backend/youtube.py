import os
from datetime import datetime, timezone

import isodate
from fastapi import HTTPException
from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from .database import (
    get_last_sync_time,
    get_shorts_count,
    get_user_by_id,
    update_last_sync,
    update_user_tokens,
    upsert_shorts,
)


def _is_short(duration_str: str) -> bool:
    try:
        return isodate.parse_duration(duration_str).total_seconds() <= 180
    except Exception:
        return False


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

    # Step 2: batch-fetch durations and titles, filter Shorts
    liked_map = {vid: ts for vid, ts in video_liked}
    all_ids = list(liked_map.keys())
    shorts: list[dict] = []

    for i in range(0, len(all_ids), 50):
        batch = all_ids[i : i + 50]
        resp = youtube.videos().list(
            id=",".join(batch),
            part="contentDetails,snippet",
        ).execute()

        for item in resp.get("items", []):
            vid_id = item["id"]
            duration = item["contentDetails"].get("duration", "")
            title = item["snippet"].get("title", "")
            if _is_short(duration):
                shorts.append({
                    "video_id": vid_id,
                    "title": title,
                    "liked_at": liked_map.get(vid_id, ""),
                })

    added = await upsert_shorts(user_id, shorts)
    await update_last_sync(user_id)
    total = await get_shorts_count(user_id)

    return {"added": added, "total": total}
