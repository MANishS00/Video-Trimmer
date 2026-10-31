
import os
import tempfile
from pathlib import Path

import yt_dlp
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.supabase_service import save_metadata_to_supabase, upload_file_to_supabase
from app.services.video_splitter import FFMPEG_BIN

router = APIRouter(prefix="/videos", tags=["Videos"])


class YouTubeDownloadRequest(BaseModel):
    youtube_url: str
    cookies_file: str | None = None
    cookies_from_browser: str | None = None


def _build_download_options(
    cookies_file: str | None = None,
    cookies_from_browser: str | None = None,
):
    cookie_path = cookies_file or os.getenv("YOUTUBE_COOKIES_FILE") or os.getenv("YT_COOKIES_FILE")
    cookie_browser = cookies_from_browser or os.getenv("YOUTUBE_COOKIES_FROM_BROWSER") or os.getenv("YT_COOKIES_FROM_BROWSER")

    options = {
        "outtmpl": "%(id)s.%(ext)s",
        "format": "bestvideo+bestaudio/best",
        "merge_output_format": "mp4",
        "ffmpeg_location": str(Path(FFMPEG_BIN).resolve()),
        "extractor_args": {
            "youtube": {
                "player_client": ["android", "tv_embedded", "web", "mweb"],
                "player_skip": ["configs", "webpage"],
            }
        },
        "noplaylist": True,
        "restrictfilenames": True,
        "quiet": True,
        "no_warnings": True,
        "nocheckcertificate": True,
        "geo_bypass": True,
        "retries": 10,
        "fragment_retries": 10,
        "http_headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        },
    }

    if cookie_path and Path(cookie_path).exists():
        options["cookies"] = str(Path(cookie_path))
    elif cookie_path:
        options["cookies"] = str(Path(cookie_path))

    if cookie_browser:
        options["cookiesfrombrowser"] = [cookie_browser] if cookie_browser != "all" else "all"

    return options


@router.post("/download")
def download_video(request: YouTubeDownloadRequest):
    url = request.youtube_url.strip()

    if not url:
        raise HTTPException(status_code=400, detail="YouTube URL is required.")

    if "youtube.com" not in url and "youtu.be" not in url:
        raise HTTPException(status_code=400, detail="Only YouTube video URLs are supported.")

    temp_dir = Path(tempfile.mkdtemp(prefix="yt_download_"))
    destination = None

    try:
        options = _build_download_options(
            cookies_file=request.cookies_file,
            cookies_from_browser=request.cookies_from_browser,
        )
        options["outtmpl"] = str(temp_dir / "%(id)s.%(ext)s")

        with yt_dlp.YoutubeDL(options) as ydl:
            info = ydl.extract_info(url, download=True)

        if not info:
            raise HTTPException(status_code=400, detail="YouTube returned no video information for this URL.")

        video_id = info.get("id")
        candidate = Path(info["_filename"]) if info.get("_filename") else None
        if candidate is not None and candidate.exists():
            destination = candidate

        if destination is None:
            matches = sorted(temp_dir.glob(f"{video_id}.*"), key=lambda path: path.stat().st_size if path.exists() else 0, reverse=True)
            if matches:
                destination = matches[0]

        if destination is None or not destination.exists():
            raise HTTPException(
                status_code=404,
                detail=f"Video download completed, but the output file could not be located for video ID {video_id}.",
            )

        file_size = destination.stat().st_size
        supabase_record = upload_file_to_supabase(
            destination,
            bucket_name="youtube-videos",
            object_name=f"{video_id}/{destination.name}",
            content_type="video/mp4",
        )

        if supabase_record is None:
            raise HTTPException(
                status_code=502,
                detail="Supabase upload failed: no storage response was returned.",
            )

        metadata = {
            "video_id": video_id,
            "title": info.get("title"),
            "filename": destination.name,
            "youtube_url": url,
            "file_url": supabase_record["public_url"],
            "storage_bucket": "youtube-videos",
            "size_bytes": file_size,
            "source": "youtube",
        }
        save_metadata_to_supabase("videos", metadata)

        return {
            "message": "Video downloaded successfully",
            "video_id": video_id,
            "title": info.get("title"),
            "filename": destination.name,
            "size": file_size,
            "youtube_url": url,
            "download_path": None,
            "supabase_url": supabase_record["public_url"],
            "supabase": supabase_record,
        }

    except HTTPException:
        raise
    except Exception as exc:
        detail = str(exc).strip() or "Failed to download the YouTube video. Check the URL and try again."
        lower_detail = detail.lower()

        if "sign in to confirm you\'re not a bot" in lower_detail or "cookies" in lower_detail:
            raise HTTPException(
                status_code=401,
                detail=(
                    "YouTube is blocking this video as bot traffic. "
                    "Pass a browser cookie file in the request as cookies_file or set YOUTUBE_COOKIES_FILE "
                    "in the environment, or provide cookies_from_browser such as 'chrome' or 'firefox'."
                ),
            ) from exc

        raise HTTPException(
            status_code=400,
            detail=f"Unable to download this public YouTube video: [{type(exc).__name__}] {detail}",
        )
    finally:
        if destination is not None and destination.exists():
            destination.unlink(missing_ok=True)
        if temp_dir.exists():
            for file in temp_dir.iterdir():
                if file.is_file():
                    file.unlink(missing_ok=True)
            if not any(temp_dir.iterdir()):
                temp_dir.rmdir()
