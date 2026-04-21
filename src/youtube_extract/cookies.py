"""Carrega cookies Netscape/Mozilla num Session do requests (opcional)."""

from __future__ import annotations

import http.cookiejar
from pathlib import Path

from requests import Session


def session_with_netscape_cookies(cookie_path: str | Path) -> Session:
    """
    Lê ficheiro no formato Netscape (exportável de navegadores / yt-dlp --cookies-from-browser).
    Pode ajudar em vídeos com restrição de idade ou login, quando as cookies forem válidas.
    """
    path = Path(cookie_path).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Ficheiro de cookies não encontrado: {path}")

    jar = http.cookiejar.MozillaCookieJar(str(path))
    jar.load(ignore_discard=True, ignore_expires=True)
    session = Session()
    session.cookies = jar
    return session
