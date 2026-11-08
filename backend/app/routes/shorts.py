
import shutil
import tempfile
import urllib.request
from pathlib import Path

from fastapi import APIRouter, Body, HTTPException

from app.services.supabase_service import get_supabase_client, save_metadata_to_supabase, upload_file_to_supabase
from app.services.video_splitter import split_video

router = APIRouter(prefix="/shorts", tags=["Shorts"])


def _normalize_video_id(video_id: str | None) -> str:
    if video_id is None:
        return ""
    return str(video_id).strip().strip('"').strip("'")


def _download_source_video_from_supabase(video_id: str) -> Path:
    client = get_supabase_client()
    if client is None:
        raise RuntimeError("Supabase is not configured with a valid service role key.")

    rows = client.table("videos").select("file_url, filename").eq("video_id", video_id).execute()
    records = rows.data or []
    if not records:
        raise FileNotFoundError(f"No source video found in Supabase for video_id: {video_id}")

    file_url = records[0].get("file_url")
    if not file_url:
        raise FileNotFoundError(f"Source video URL is missing in Supabase for video_id: {video_id}")

    temp_dir = Path(tempfile.mkdtemp(prefix=f"shorts_source_{video_id}_"))
    target_path = temp_dir / records[0].get("filename", f"{video_id}.mp4")
    try:
        urllib.request.urlretrieve(file_url, target_path)
    except Exception as exc:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise RuntimeError(f"Failed to download source video from Supabase: {exc}") from exc

    return target_path


@router.post("/split")
def create_shorts_from_request(payload: dict | None = Body(default=None)):
    if not payload:
        raise HTTPException(status_code=400, detail="Request body is required and must include a video_id.")

    raw_video_id = None
    for key, value in payload.items():
        if str(key).strip() == "video_id":
            raw_video_id = value
            break

    if raw_video_id is None:
        raise HTTPException(status_code=400, detail="video_id is required in the request body.")

    return create_shorts(str(raw_video_id))


@router.post("/split/{video_id}")
def create_shorts(video_id: str):
    """Split a source video stored in Supabase into 30-second shorts."""
    normalized_id = _normalize_video_id(video_id)
    if not normalized_id:
        raise HTTPException(status_code=400, detail="video_id is required.")
    normalized_id = Path(normalized_id).stem if Path(normalized_id).suffix else normalized_id
    temp_root = Path(tempfile.mkdtemp(prefix=f"shorts_{normalized_id}_"))

    try:
        source_path = None
        for candidate in [temp_root / f"{normalized_id}.mp4", temp_root / "source.mp4"]:
            if candidate.exists():
                source_path = candidate
                break

        if source_path is None:
            try:
                source_path = _download_source_video_from_supabase(normalized_id)
            except Exception as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc

        output_dir = temp_root / "generated"
        result = split_video(str(source_path), str(output_dir), clip_duration=30)

        uploaded_shorts = []
        for clip in result["clips"]:
            clip_path = output_dir / clip["filename"]
            if not clip_path.exists():
                continue

            try:
                upload_data = upload_file_to_supabase(
                    clip_path,
                    bucket_name="youtube-shorts",
                    object_name=f"{normalized_id}/{clip['filename']}",
                    content_type="video/mp4",
                )
                metadata_payload = {
                    "video_id": normalized_id,
                    "part": clip["part"],
                    "filename": clip["filename"],
                    "start_seconds": clip["start"],
                    "duration_seconds": clip["duration"],
                    "file_url": upload_data["public_url"] if upload_data else None,
                    "storage_bucket": "youtube-shorts",
                    "source_file": str(source_path),
                }
                save_metadata_to_supabase("shorts", metadata_payload)

                public_url = upload_data["public_url"] if upload_data else None
                if upload_data:
                    clip_path.unlink(missing_ok=True)

                uploaded_shorts.append({
                    "part": clip["part"],
                    "filename": clip["filename"],
                    "public_url": public_url,
                })
            except Exception as exc:
                raise HTTPException(
                    status_code=502,
                    detail=f"Supabase upload failed for short clip {clip['filename']}: {exc}",
                ) from exc

        result["supabase_uploads"] = uploaded_shorts
        return {
            "message": "Shorts generated successfully",
            "video_id": video_id,
            "source_file": str(source_path),
            "clips": result,
        }

    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(status_code=500, detail=f"Video processing failed: {error}") from error
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)
