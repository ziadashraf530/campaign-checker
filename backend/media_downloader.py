from __future__ import annotations

import hashlib
import os
import shutil
import urllib.request
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

IMAGE_EXTS = {"png", "jpg", "jpeg", "webp", "bmp", "gif", "tiff"}
VIDEO_EXTS = {"mp4", "avi", "mov", "mkv", "webm"}
SUPPORTED_EXTS = IMAGE_EXTS | VIDEO_EXTS

DOWNLOAD_DIR = Path(__file__).resolve().parent / "download_cache"


def ensure_download_dir() -> Path:
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    return DOWNLOAD_DIR


def is_image_file(path: str) -> bool:
    return _ext_from_path(path) in IMAGE_EXTS


def is_video_file(path: str) -> bool:
    return _ext_from_path(path) in VIDEO_EXTS


def is_supported_media_file(path: str) -> bool:
    return _ext_from_path(path) in SUPPORTED_EXTS


def download_media_from_url(url: str, download_dir: Optional[Path] = None) -> tuple[list[str], Optional[str]]:
    download_dir = Path(download_dir) if download_dir else ensure_download_dir()

    if _is_direct_media_url(url):
        return _download_direct(url, download_dir)

    return _download_with_ytdlp(url, download_dir)


def _download_direct(url: str, download_dir: Path) -> tuple[list[str], Optional[str]]:
    ext = _ext_from_url(url) or "bin"
    name = hashlib.md5(url.encode("utf-8")).hexdigest()
    filename = f"direct_{name}.{ext}"
    path = download_dir / filename

    try:
        with urllib.request.urlopen(url, timeout=30) as response, open(path, "wb") as handle:
            shutil.copyfileobj(response, handle)
    except Exception as exc:
        return [], f"Direct download failed: {exc}"

    if not is_supported_media_file(str(path)):
        return [], "Downloaded file is not a supported media type"

    return [str(path)], None


def _download_with_ytdlp(url: str, download_dir: Path) -> tuple[list[str], Optional[str]]:
    try:
        from yt_dlp import YoutubeDL
    except Exception as exc:
        return [], f"yt-dlp not available: {exc}"

    downloaded: list[str] = []

    def _hook(data: dict) -> None:
        if data.get("status") == "finished" and data.get("filename"):
            downloaded.append(data["filename"])

    ydl_opts = {
        "outtmpl": str(download_dir / "%(extractor)s_%(id)s.%(ext)s"),
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "format": "bestvideo+bestaudio/best",
        "merge_output_format": "mp4",
        "progress_hooks": [_hook],
    }

    try:
        with YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
    except Exception as exc:
        return [], f"yt-dlp download failed: {exc}"

    filtered = [path for path in downloaded if is_supported_media_file(path)]
    if not filtered:
        return [], "No supported media files were downloaded"

    return filtered, None


def _ext_from_path(path: str) -> str:
    return os.path.splitext(path)[1].lower().lstrip(".")


def _ext_from_url(url: str) -> str:
    parsed = urlparse(url)
    ext = os.path.splitext(parsed.path)[1].lower().lstrip(".")
    return ext if ext in SUPPORTED_EXTS else ""


def _is_direct_media_url(url: str) -> bool:
    return bool(_ext_from_url(url))
