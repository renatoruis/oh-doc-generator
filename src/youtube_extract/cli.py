"""Interface de linha de comando."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from youtube_transcript_api import (
    AgeRestricted,
    IpBlocked,
    NoTranscriptFound,
    PoTokenRequired,
    RequestBlocked,
    TranscriptsDisabled,
    VideoUnavailable,
    VideoUnplayable,
    YouTubeTranscriptApiException,
)

from youtube_extract.cookies import session_with_netscape_cookies
from youtube_extract.extract import (
    fetch_transcript,
    format_fetched,
    list_available_transcripts,
    proxy_from_urls,
    resolve_format,
    transcript_to_json_document,
    write_json_file,
)
from youtube_extract.video_id import extract_video_id


def _parse_languages(langs: str) -> list[str]:
    parts = [p.strip() for p in langs.split(",") if p.strip()]
    return parts or ["en"]


def _friendly_error(exc: BaseException, video_id: str) -> str:
    if isinstance(exc, TranscriptsDisabled):
        return (
            f"O vídeo {video_id} tem legendas desativadas pelo criador. "
            "Não há transcrição disponível para extrair."
        )
    if isinstance(exc, NoTranscriptFound):
        return (
            f"Nenhuma legenda encontrada para o vídeo {video_id} nos idiomas pedidos. "
            "Tente --list para ver idiomas disponíveis ou --lang com outros códigos."
        )
    if isinstance(exc, VideoUnavailable):
        return f"O vídeo {video_id} não está disponível (removido ou privado)."
    if isinstance(exc, VideoUnplayable):
        return f"O vídeo {video_id} não pode ser reproduzido (pode exigir login ou estar bloqueado)."
    if isinstance(exc, AgeRestricted):
        return (
            f"O vídeo {video_id} tem restrição de idade. "
            "Experimente --cookies com um ficheiro Netscape exportado do navegador."
        )
    if isinstance(exc, IpBlocked):
        return (
            "O YouTube bloqueou o IP (429). Tente mais tarde ou use --proxy-http / --proxy-https."
        )
    if isinstance(exc, RequestBlocked):
        return (
            "Pedido bloqueado pelo YouTube. Tente mais tarde ou use proxies conforme a documentação da biblioteca."
        )
    if isinstance(exc, PoTokenRequired):
        return (
            "O YouTube exige token de verificação (PoToken) para este pedido. "
            "Atualize youtube-transcript-api ou veja issues do projeto upstream."
        )
    if isinstance(exc, YouTubeTranscriptApiException):
        return f"Erro ao obter transcrição: {exc}"
    return f"Erro: {exc}"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Extrai transcrição (legendas) de vídeos do YouTube sem API paga.",
    )
    parser.add_argument(
        "url",
        nargs="?",
        help="URL do vídeo ou ID de 11 caracteres",
    )
    parser.add_argument(
        "-u",
        "--url",
        dest="url_flag",
        metavar="URL",
        help="URL do vídeo (alternativa ao argumento posicional)",
    )
    parser.add_argument(
        "-f",
        "--format",
        default="txt",
        metavar="FMT",
        help="Saída: txt, json, srt ou vtt (default: txt)",
    )
    parser.add_argument(
        "-l",
        "--lang",
        default="pt,en",
        metavar="LANGS",
        help="Códigos de idioma por ordem de preferência, separados por vírgula (default: pt,en)",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="Lista legendas disponíveis e sai",
    )
    parser.add_argument(
        "--preserve-formatting",
        action="store_true",
        help="Mantém formatação HTML parcial nas linhas (quando aplicável)",
    )
    parser.add_argument(
        "--cookies",
        metavar="PATH",
        help="Ficheiro de cookies Netscape (exportável do navegador) para vídeos restritos",
    )
    parser.add_argument(
        "--proxy-http",
        default="",
        metavar="URL",
        help="Proxy HTTP (ex.: http://user:pass@host:port)",
    )
    parser.add_argument(
        "--proxy-https",
        default="",
        metavar="URL",
        help="Proxy HTTPS",
    )
    parser.add_argument(
        "--json-out",
        default=None,
        metavar="PATH",
        help="Caminho do ficheiro JSON (default: <video_id>.json no diretório atual)",
    )
    parser.add_argument(
        "--no-json-file",
        action="store_true",
        help="Não gravar ficheiro JSON (apenas saída em stdout conforme -f)",
    )

    args = parser.parse_args(list(argv) if argv is not None else None)

    target = args.url or args.url_flag
    if not target:
        parser.error("Indique a URL ou o ID do vídeo (argumento posicional ou -u).")

    try:
        resolve_format(args.format)
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 2

    try:
        video_id = extract_video_id(target)
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 2

    languages = _parse_languages(args.lang)
    http_client = None
    if args.cookies:
        try:
            http_client = session_with_netscape_cookies(args.cookies)
        except OSError as e:
            print(str(e), file=sys.stderr)
            return 2

    proxy_config = proxy_from_urls(
        args.proxy_http or None,
        args.proxy_https or None,
    )

    try:
        if args.list:
            tlist = list_available_transcripts(
                video_id,
                proxy_config=proxy_config,
                http_client=http_client,
            )
            print(str(tlist))
            return 0

        transcript = fetch_transcript(
            video_id,
            languages,
            preserve_formatting=args.preserve_formatting,
            proxy_config=proxy_config,
            http_client=http_client,
        )

        if not args.no_json_file:
            json_path = args.json_out or f"{video_id}.json"
            written = write_json_file(transcript, json_path)
            print(f"JSON guardado em: {written}", file=sys.stderr)

        fmt = args.format.strip().lower()
        if fmt == "json":
            print(transcript_to_json_document(transcript))
        else:
            print(format_fetched(transcript, args.format))
        return 0
    except Exception as exc:
        print(_friendly_error(exc, video_id), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
