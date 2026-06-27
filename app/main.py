import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from api.auth import router as auth_router
from api.shorts import router as shorts_router

BASE_DIR = Path(__file__).resolve().parent.parent
PUBLIC_DIR = BASE_DIR / "static"


def create_app() -> FastAPI:
    load_dotenv(BASE_DIR / ".env")

    app = FastAPI()

    app.add_middleware(SessionMiddleware, secret_key=os.environ["SESSION_SECRET"])
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:3000",
            "http://localhost:5173",
            "http://localhost:8000",
            "https://ssg.up.railway.app",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(auth_router, prefix="/auth")
    app.include_router(shorts_router, prefix="/api")
    app.mount("/", StaticFiles(directory=PUBLIC_DIR, html=True), name="public")

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn
    import os

    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=True)
