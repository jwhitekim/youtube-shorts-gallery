import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from backend.auth import router as auth_router
from backend.database import delete_short, get_shorts, reorder_shorts
from backend.youtube import sync_liked_shorts

app = FastAPI()

app.add_middleware(SessionMiddleware, secret_key=os.environ["SESSION_SECRET"])
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:8000",
        "https://shorts-gallery-production.up.railway.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/auth")


def _require_user(request: Request) -> str:
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user_id


@app.get("/api/shorts/sync")
async def api_sync_shorts(request: Request):
    user_id = _require_user(request)
    return await sync_liked_shorts(user_id)


@app.get("/api/shorts")
async def api_list_shorts(request: Request):
    user_id = _require_user(request)
    return await get_shorts(user_id)


@app.delete("/api/shorts/{video_id}")
async def api_delete_short(video_id: str, request: Request):
    user_id = _require_user(request)
    await delete_short(user_id, video_id)
    return {"status": "ok"}


@app.patch("/api/shorts/reorder")
async def api_reorder_shorts(request: Request):
    user_id = _require_user(request)
    body = await request.json()
    video_ids: list[str] = body.get("video_ids", [])
    await reorder_shorts(user_id, video_ids)
    return {"status": "ok"}


app.mount("/", StaticFiles(directory="static", html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
