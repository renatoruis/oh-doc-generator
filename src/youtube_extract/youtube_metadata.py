"""Metadados públicos do YouTube via yt-dlp (Python API)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_MONTHS_PT = (
    "janeiro",
    "fevereiro",
    "março",
    "abril",
    "maio",
    "junho",
    "julho",
    "agosto",
    "setembro",
    "outubro",
    "novembro",
    "dezembro",
)

_MONTHS_EN = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)


def _parse_yyyymmdd(upload_date: str | None) -> tuple[int, int, int] | None:
    if not upload_date or len(upload_date) != 8 or not upload_date.isdigit():
        return None
    y = int(upload_date[:4])
    m = int(upload_date[4:6])
    d = int(upload_date[6:8])
    if not 1 <= m <= 12 or not 1 <= d <= 31:
        return None
    return y, m, d


def format_cult_date_pt(upload_date: str | None) -> str | None:
    """Converte YYYYMMDD (yt-dlp) para texto legível em PT."""
    parsed = _parse_yyyymmdd(upload_date)
    if not parsed:
        return None
    y, m, d = parsed
    return f"{d} de {_MONTHS_PT[m - 1]} de {y}"


def format_cult_date_en(upload_date: str | None) -> str | None:
    """Converte YYYYMMDD para texto legível em EN (ex.: '19 April 2026')."""
    parsed = _parse_yyyymmdd(upload_date)
    if not parsed:
        return None
    y, m, d = parsed
    return f"{d} {_MONTHS_EN[m - 1]} {y}"


def fetch_youtube_metadata(url: str) -> dict[str, Any]:
    """
    Obtém título, data de publicação, estado live, etc. via yt_dlp Python API.
    Devolve dict vazio (ou com `_fetch_error`) se yt-dlp falhar — o pipeline continua só com transcrição.
    """
    try:
        from yt_dlp import YoutubeDL
        from yt_dlp.utils import DownloadError
    except ImportError:
        return {"_fetch_error": "yt_dlp não está instalado"}

    opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "extract_flat": False,
    }

    try:
        with YoutubeDL(opts) as ydl:
            raw = ydl.extract_info(url, download=False)
    except DownloadError as exc:
        return {"_fetch_error": str(exc)[:500]}
    except Exception as exc:  # pragma: no cover - defensive
        return {"_fetch_error": f"{type(exc).__name__}: {exc}"[:500]}

    if not isinstance(raw, dict):
        return {}

    upload_date = raw.get("upload_date")
    return {
        "title": raw.get("title"),
        "id": raw.get("id"),
        "upload_date": upload_date,
        "cult_date_label_pt": format_cult_date_pt(upload_date),
        "cult_date_label_en": format_cult_date_en(upload_date),
        "live_status": raw.get("live_status"),
        "was_live": raw.get("was_live"),
        "duration": raw.get("duration"),
        "webpage_url": raw.get("webpage_url"),
        "channel": raw.get("channel") or raw.get("uploader"),
        "description": (raw.get("description") or "")[:2000] or None,
        "thumbnail": raw.get("thumbnail"),
    }


def write_metadata_json(path: str | Path, data: dict[str, Any]) -> Path:
    p = Path(path).expanduser().resolve()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return p
