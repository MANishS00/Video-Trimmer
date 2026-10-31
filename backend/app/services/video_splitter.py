
import os
import re
import shutil
import subprocess
from pathlib import Path


def resolve_ffmpeg_path():
    candidates = []

    try:
        from imageio_ffmpeg import get_ffmpeg_exe
        candidates.append(get_ffmpeg_exe())
    except Exception:
        pass

    for command in ["ffmpeg", "ffmpeg.exe"]:
        found = shutil.which(command)
        if found:
            candidates.append(found)

    common_paths = [
        r"C:\ffmpeg\bin\ffmpeg.exe",
        r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
        r"C:\Program Files (x86)\ffmpeg\bin\ffmpeg.exe",
    ]
    candidates.extend(common_paths)

    for candidate in candidates:
        if not candidate:
            continue
        path = Path(candidate).expanduser()
        if path.exists():
            return str(path)

    return shutil.which("ffmpeg") or "ffmpeg"


FFMPEG_BIN = resolve_ffmpeg_path()


def ensure_ffmpeg_available():
    if not FFMPEG_BIN or not Path(FFMPEG_BIN).exists():
        raise FileNotFoundError(
            "FFmpeg executable was not found. Install ffmpeg or imageio-ffmpeg in this environment "
            "and make sure it is available on PATH."
        )


def get_video_duration(video_path: str) -> float:
    """Get video duration using FFmpeg metadata."""
    ensure_ffmpeg_available()

    result = subprocess.run(
        [
            FFMPEG_BIN,
            "-hide_banner",
            "-i", video_path,
            "-f", "null",
            "-"
        ],
        capture_output=True,
        text=True,
        check=False
    )

    output = (result.stderr or result.stdout or "")
    match = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.\d+)", output)

    if not match:
        raise ValueError(f"Could not determine video duration for: {video_path}")

    hours, minutes, seconds = match.groups()
    return float(hours) * 3600 + float(minutes) * 60 + float(seconds)


def split_video(
    video_path: str,
    output_dir: str,
    clip_duration: int = 30
):
    """Split a video into 30-second shorts. Discard a final short shorter than 15 seconds."""
    ensure_ffmpeg_available()

    source = Path(video_path)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    duration = get_video_duration(str(source))
    clips = []
    start = 0.0
    part_number = 1

    while start < duration:
        remaining = duration - start

        if remaining < 15:
            break

        current_duration = min(clip_duration, remaining)

        if remaining < clip_duration and remaining < 15:
            break

        filename = f"part{part_number}.mp4"
        output_path = output / filename

        video_filter = (
            "scale=1080:1920:force_original_aspect_ratio=decrease,"
            "pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black,"
            "drawtext=text='Part %d':fontcolor=white:fontsize=56:fontfile='arial.ttf':x=(w-text_w)/2:y=180:shadowcolor=black@0.8:shadowx=2:shadowy=2:box=1:boxcolor=black@0.25:boxborderw=18"
        ) % part_number

        subprocess.run(
            [
                FFMPEG_BIN,
                "-y",
                "-ss", str(start),
                "-i", str(source),
                "-t", str(current_duration),
                "-map", "0:v:0",
                "-map", "0:a?",
                "-vf", video_filter,
                "-c:v", "libx264",
                "-preset", "medium",
                "-crf", "18",
                "-pix_fmt", "yuv420p",
                "-c:a", "aac",
                "-ar", "48000",
                "-ac", "2",
                "-b:a", "192k",
                "-movflags", "+faststart",
                str(output_path)
            ],
            capture_output=True,
            text=True,
            check=True
        )

        clips.append({
            "part": part_number,
            "filename": filename,
            "start": start,
            "duration": current_duration
        })

        start += current_duration
        part_number += 1

    return {
        "total_parts": len(clips),
        "video_duration": duration,
        "clips": clips
    }
