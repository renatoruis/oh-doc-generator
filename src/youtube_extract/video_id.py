"""Extrai o ID de 11 caracteres de URLs do YouTube ou valida um ID cru."""

from __future__ import annotations

import re
from urllib.parse import parse_qs, urlparse

_VIDEO_ID = re.compile(r"^[a-zA-Z0-9_-]{11}$")


def extract_video_id(url_or_id: str) -> str:
    """
    Aceita URL (watch, youtu.be, shorts, live, embed) ou o próprio video ID.
    """
    s = url_or_id.strip()
    if _VIDEO_ID.fullmatch(s):
        return s

    raw = s if "://" in s else f"https://{s}"
    parsed = urlparse(raw)
    host = (parsed.netloc or "").lower()
    path = (parsed.path or "").strip("/")
    segments = [p for p in path.split("/") if p]

    if "youtu.be" in host and segments:
        if _VIDEO_ID.fullmatch(segments[0]):
            return segments[0]

    if "youtube.com" in host or "youtube-nocookie.com" in host:
        if segments and segments[0] == "watch":
            v = parse_qs(parsed.query).get("v", [None])[0]
            if v and _VIDEO_ID.fullmatch(v):
                return v
        for kind in ("embed", "v", "shorts", "live"):
            if len(segments) >= 2 and segments[0] == kind:
                if _VIDEO_ID.fullmatch(segments[1]):
                    return segments[1]

    raise ValueError(
        "Não foi possível obter o ID do vídeo. Envie uma URL válida do YouTube "
        "ou o ID de 11 caracteres."
    )
