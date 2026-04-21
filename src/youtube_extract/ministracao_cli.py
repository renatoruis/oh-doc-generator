"""CLI: URL → transcrição → segmentação → resumo da ministração (PT-PT + EN) via Claude Code CLI."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from youtube_extract.ministracao import DEFAULT_MAX_CHARS, run_ministracao_workflow


def _parse_languages(s: str) -> list[str]:
    parts = [p.strip() for p in s.split(",") if p.strip()]
    return parts or ["pt", "en"]


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Recebe um URL do YouTube, extrai a transcrição, segmenta o culto com Claude "
            "e gera o resumo da ministração (PT-PT + EN + perguntas Open Groups)."
        ),
    )
    parser.add_argument("url", help="URL do vídeo ou ID (11 caracteres)")
    parser.add_argument("-o", "--out-dir", default=".", help="Pasta de saída (default: atual)")
    parser.add_argument("-l", "--lang", default="pt,en", help="Idiomas das legendas (default: pt,en)")
    parser.add_argument(
        "--with-timestamps",
        action="store_true",
        help="Inclui [MM:SS] em cada linha da transcrição no prompt",
    )
    parser.add_argument(
        "--max-chars",
        type=int,
        default=DEFAULT_MAX_CHARS,
        help=f"Máx. caracteres no prompt (default: {DEFAULT_MAX_CHARS})",
    )
    parser.add_argument("--cookies", metavar="PATH", help="Cookies Netscape (vídeo restrito)")
    parser.add_argument("--proxy-http", default="", metavar="URL")
    parser.add_argument("--proxy-https", default="", metavar="URL")
    parser.add_argument(
        "--skip-claude",
        action="store_true",
        help="Só extrai e grava JSON + ficheiro de prompt (não executa o Claude)",
    )
    parser.add_argument(
        "--skip-segment",
        action="store_true",
        help="Salta a segmentação do culto (resumo sobre transcrição inteira)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Refaz segmentação e resumo mesmo que artefactos já existam",
    )
    parser.add_argument(
        "--claude-bin",
        default=None,
        help="Caminho para o executável `claude` (default: PATH)",
    )
    parser.add_argument(
        "--claude-extra",
        default=None,
        metavar="STRING",
        help="Argumentos extra para o Claude CLI (shlex). Default: vazio.",
    )

    args = parser.parse_args(list(argv) if argv is not None else None)

    try:
        result = run_ministracao_workflow(
            args.url,
            out_dir=Path(args.out_dir),
            languages=_parse_languages(args.lang),
            include_timestamps=args.with_timestamps,
            max_chars=args.max_chars,
            cookie_path=args.cookies,
            proxy_http=args.proxy_http or None,
            proxy_https=args.proxy_https or None,
            skip_claude=args.skip_claude,
            skip_segment=args.skip_segment,
            force=args.force,
            claude_bin=args.claude_bin,
            claude_extra=args.claude_extra,
            show_progress=True,
        )
    except (RuntimeError, ValueError, OSError) as e:
        print(str(e), file=sys.stderr)
        return 1

    vid = result["video_id"]
    print(f"video_id: {vid}", file=sys.stderr)
    print(f"JSON:     {result['json']}", file=sys.stderr)
    if result.get("prompt"):
        print(f"Prompt:   {result['prompt']}", file=sys.stderr)

    if args.skip_claude:
        print(
            "\nPara gerar o resumo depois: corre o Claude e passa o conteúdo de "
            "`ministracao_prompt.md`.",
            file=sys.stderr,
        )
        return 0

    code = result.get("claude_code")
    if result.get("resumo"):
        print(f"Resumo:   {result['resumo']}", file=sys.stderr)
    return 0 if (code is None or code == 0) else 1


if __name__ == "__main__":
    raise SystemExit(main())
