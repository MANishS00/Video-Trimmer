
import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes import shorts
from app.routes import videos

BASE_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BASE_DIR / ".env")

allowed_origins = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
    if origin.strip()
]

app = FastAPI(
    title="AI YouTube Shorts Generator",
    description="Download a YouTube video by URL and create short clips from it",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(videos.router)
app.include_router(shorts.router)


@app.get("/")
def home():
    return {
        "message": "AI Shorts Generator API is running!"
    }

@app.get("/health")
def health():
    return {
        "status": "healthy"
    }
