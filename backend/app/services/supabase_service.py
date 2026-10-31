import base64
import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

from dotenv import load_dotenv
from supabase import create_client

BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BASE_DIR / ".env")


def _decode_jwt_role(token: str):
    if not token or "." not in token:
        return None

    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        decoded = base64.urlsafe_b64decode(payload.encode()).decode()
        return json.loads(decoded).get("role")
    except Exception:
        return None


def get_supabase_client():
    url = os.getenv("SUPABASE_URL")
    key = (
        os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        or os.getenv("SUPABASE_KEY")
    )

    if not url or not key:
        return None

    role = _decode_jwt_role(key)
    if role != "service_role":
        return None

    return create_client(url, key)


def is_supabase_configured() -> bool:
    url = os.getenv("SUPABASE_URL")
    key = (
        os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        or os.getenv("SUPABASE_KEY")
    )

    if not url or not key:
        return False

    return _decode_jwt_role(key) == "service_role"


def upload_file_to_supabase(
    file_path: str | Path,
    bucket_name: str,
    object_name: Optional[str] = None,
    content_type: Optional[str] = None,
):
    client = get_supabase_client()
    if client is None:
        raise RuntimeError(
            "Supabase is not configured with a valid service_role key. "
            "Update SUPABASE_SERVICE_ROLE_KEY in backend/.env with the project service role secret."
        )

    file = Path(file_path)
    if not file.exists():
        raise FileNotFoundError(f"File not found for Supabase upload: {file}")

    target_name = object_name or file.name
    with file.open("rb") as upload_file:
        upload_result = client.storage.from_(bucket_name).upload(
            target_name,
            upload_file.read(),
            {"content-type": content_type or "application/octet-stream", "upsert": "true"},
        )

    public_url = client.storage.from_(bucket_name).get_public_url(target_name)

    return {
        "bucket": bucket_name,
        "object_name": target_name,
        "public_url": public_url,
        "storage_response": upload_result,
    }


def save_metadata_to_supabase(table_name: str, payload: Dict[str, Any]):
    client = get_supabase_client()
    if client is None:
        raise RuntimeError(
            "Supabase is not configured with a valid service_role key. "
            "Update SUPABASE_SERVICE_ROLE_KEY in backend/.env with the project service role secret."
        )

    try:
        response = client.table(table_name).insert(payload).execute()
        return response.data
    except Exception as exc:
        raise RuntimeError(f"Supabase insert into {table_name} failed: {exc}") from exc
