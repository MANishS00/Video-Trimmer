
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes import videos
from app.routes import shorts

BASE_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BASE_DIR / ".env")


app = FastAPI(
    title="AI YouTube Shorts Generator",
    description="Download a YouTube video by URL and create short clips from it",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
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
