"""Busca transcrição e formata saída."""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import asdict
from pathlib import Path

from requests import Session
from youtube_transcript_api import FetchedTranscript, YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    NoTranscriptFound,
    TranscriptsDisabled,
    VideoUnavailable,
    VideoUnplayable,
)
from youtube_transcript_api.formatters import FormatterLoader
from youtube_transcript_api.proxies import GenericProxyConfig, ProxyConfig

_FORMAT_ALIASES = {
    "txt": "text",
    "json": "json",
    "srt": "srt",
    "vtt": "webvtt",
    "webvtt": "webvtt",
}


class NoCaptionsAvailable(RuntimeError):
    """Vídeo não tem legendas (manuais ou auto-geradas) — caso de utilizador, não bug."""

    def __init__(self, video_id: str, reason: str, *, original: Exception | None = None) -> None:
        self.video_id = video_id
        self.reason = reason
        self.original = original
        super().__init__(f"Sem legendas para {video_id}: {reason}")


def resolve_format(fmt: str) -> str:
    key = fmt.strip().lower()
    if key not in _FORMAT_ALIASES:
        supported = ", ".join(sorted(set(_FORMAT_ALIASES.keys())))
        raise ValueError(f"Formato inválido {fmt!r}. Use: {supported}")
    return _FORMAT_ALIASES[key]


def fetch_transcript(
    video_id: str,
    languages: Iterable[str],
    *,
    preserve_formatting: bool = False,
    proxy_config: ProxyConfig | None = None,
    http_client: Session | None = None,
) -> FetchedTranscript:
    api = YouTubeTranscriptApi(proxy_config=proxy_config, http_client=http_client)
    try:
        return api.fetch(
            video_id,
            languages=languages,
            preserve_formatting=preserve_formatting,
        )
    except TranscriptsDisabled as exc:
        raise NoCaptionsAvailable(
            video_id,
            "O YouTube indica que as legendas estão desativadas ou ainda não foram geradas "
            "(comum em lives recentes).",
            original=exc,
        ) from exc
    except NoTranscriptFound as exc:
        raise NoCaptionsAvailable(
            video_id,
            f"Não existem legendas nos idiomas pedidos ({', '.join(languages) or '—'}).",
            original=exc,
        ) from exc
    except (VideoUnavailable, VideoUnplayable) as exc:
        raise NoCaptionsAvailable(
            video_id,
            "O vídeo não está disponível/jogável para o YouTube (privado, removido "
            "ou com restrição regional).",
            original=exc,
        ) from exc


def format_fetched(transcript: FetchedTranscript, output_format: str) -> str:
    internal = resolve_format(output_format)
    formatter = FormatterLoader().load(internal)
    return formatter.format_transcript(transcript)


def transcript_to_json_document(transcript: FetchedTranscript) -> str:
    """JSON com metadados e segmentos (text, start, duration)."""
    payload = {
        "video_id": transcript.video_id,
        "language": transcript.language,
        "language_code": transcript.language_code,
        "is_generated": transcript.is_generated,
        "segments": [asdict(s) for s in transcript.snippets],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def write_json_file(transcript: FetchedTranscript, path: str | Path) -> Path:
    p = Path(path).expanduser().resolve()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(transcript_to_json_document(transcript), encoding="utf-8")
    return p


def fetched_to_plain_text(
    transcript: FetchedTranscript,
    *,
    include_timestamps: bool = False,
) -> str:
    """Texto contínuo ou com [MM:SS] por linha, a partir de uma transcrição obtida."""
    from youtube_extract.summarize import segments_to_plain_text

    segs = [asdict(s) for s in transcript.snippets]
    return segments_to_plain_text(segs, include_timestamps=include_timestamps)


def fetch_and_format(
    video_id: str,
    languages: Iterable[str],
    output_format: str,
    *,
    preserve_formatting: bool = False,
    proxy_config: ProxyConfig | None = None,
    http_client: Session | None = None,
) -> str:
    transcript = fetch_transcript(
        video_id,
        languages,
        preserve_formatting=preserve_formatting,
        proxy_config=proxy_config,
        http_client=http_client,
    )
    return format_fetched(transcript, output_format)


def list_available_transcripts(
    video_id: str,
    *,
    proxy_config: ProxyConfig | None = None,
    http_client: Session | None = None,
):
    api = YouTubeTranscriptApi(proxy_config=proxy_config, http_client=http_client)
    return api.list(video_id)


def proxy_from_urls(http_proxy: str | None, https_proxy: str | None) -> ProxyConfig | None:
    if not http_proxy and not https_proxy:
        return None
    return GenericProxyConfig(
        http_url=http_proxy or "",
        https_url=https_proxy or "",
    )
